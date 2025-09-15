bl_info = {
    "name": "NX3 Importer/Exporter",
    "author": "IRLABS",
    "version": (1, 4),
    "blender": (4, 3, 2),
    "location": "File > Import / Export",
    "description": "Imports and Exports neural 3D files, .NX3, with options to apply modifiers and combine meshes.",
    "category": "Import-Export",
}

import bpy
import zipfile
import os
import tempfile
import shutil
import json

from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

# ------------------------------------------------------------------------
#    Import Operator
# ------------------------------------------------------------------------
class ImportNX3(bpy.types.Operator, ImportHelper):
    """Import a .nx3 file (renamed .zip containing .glb, .txt, .safetensor)."""
    bl_idname = "import_scene.nx3"
    bl_label = "Import/Export NX3"
    bl_options = {'UNDO'}

    filename_ext = ".nx3"
    filter_glob: StringProperty(
        default="*.nx3",
        options={'HIDDEN'},
        maxlen=255,
    )

    def apply_properties(self, obj, properties):
        """Apply custom properties to an object."""
        for key, value in properties.items():
            try:
                # Convert string values that should be numbers
                if isinstance(value, str):
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass
                if key not in obj:
                    obj[key] = value
                else:
                    del obj[key]
                    obj[key] = value
                # Ensure the property is visible in the UI
                if '_RNA_UI' not in obj:
                    obj['_RNA_UI'] = {}
                if key not in obj['_RNA_UI']:
                    obj['_RNA_UI'][key] = {"description": ""}
            except Exception as e:
                self.report({'WARNING'}, f"Failed to set property {key}: {str(e)}")

    def execute(self, context):
        nx3_path = self.filepath

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with zipfile.ZipFile(nx3_path, 'r') as zfile:
                    # Check total size before extraction (5GB limit)
                    total_size = sum(info.file_size for info in zfile.infolist())
                    if total_size > 5 * 1024 * 1024 * 1024:  # 5GB in bytes
                        self.report({'ERROR'}, f"File too large: {total_size / (1024**3):.1f}GB. Maximum allowed: 5GB")
                        return {'CANCELLED'}
                    zfile.extractall(temp_dir)
            except zipfile.BadZipFile:
                self.report({'ERROR'}, "Invalid .nx3 file (cannot unzip).")
                return {'CANCELLED'}

            # Find glb, json, and safetensor
            glb_path, json_path, safetensor_path = None, None, None
            for filename in os.listdir(temp_dir):
                lower_name = filename.lower()
                file_path = os.path.join(temp_dir, filename)

                if lower_name.endswith(".glb"):
                    glb_path = file_path
                elif lower_name.endswith(".json"):
                    json_path = file_path
                elif lower_name.endswith(".safetensor"):
                    safetensor_path = file_path

            # First load the properties from json file if it exists
            properties_data = None
            geometry_properties = None
            lora_properties = None
            if json_path and os.path.isfile(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        properties_data = data.get("properties")
                        geometry_properties = data.get("Geometry_properties")
                        lora_properties = data.get("Lora_properties")
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to load properties: {str(e)}")

            # Store the names of objects before import
            initial_objects = set(obj.name for obj in bpy.data.objects)

            # Import glb if found
            if glb_path and os.path.isfile(glb_path):
                bpy.ops.import_scene.gltf(filepath=glb_path)
                
                # Get newly imported objects
                new_objects = [obj for obj in bpy.data.objects if obj.name not in initial_objects]
                
                # Report additional metadata if available
                if geometry_properties:
                    self.report({'INFO'}, f"Geometry: {geometry_properties.get('name', 'Unknown')} ({geometry_properties.get('3d_format', 'Unknown')})")
                if lora_properties:
                    self.report({'INFO'}, f"LoRA: {lora_properties.get('Lora_source', 'Unknown')} - {lora_properties.get('Lora_destination', 'No destination')}")
                
                # Apply properties if we have them
                if properties_data and new_objects:
                    try:
                        if isinstance(properties_data, dict):
                            has_nested_dicts = any(isinstance(v, dict) for v in properties_data.values())
                            
                            if has_nested_dicts:
                                self.report({'INFO'}, "Found multiple property sets")
                                for obj in new_objects:
                                    obj_name = obj.name
                                    base_name = obj_name.split('.')[0]
                                    if obj_name in properties_data:
                                        prop_set = properties_data[obj_name]
                                    elif base_name in properties_data:
                                        prop_set = properties_data[base_name]
                                    else:
                                        continue
                                    for key, value in prop_set.items():
                                        try:
                                            if '_RNA_UI' not in obj:
                                                obj['_RNA_UI'] = {}
                                            obj[key] = value
                                            obj['_RNA_UI'][key] = {
                                                "description": "",
                                                "default": value,
                                                "is_overridable_library": True
                                            }
                                            self.report({'INFO'}, f"Set property {key}={value} on {obj.name}")
                                        except Exception as e:
                                            self.report({'WARNING'}, f"Failed to set {key} on {obj.name}: {str(e)}")
                            else:
                                self.report({'INFO'}, "Found single property set")
                                for obj in new_objects:
                                    if obj.type == 'MESH':
                                        for key, value in properties_data.items():
                                            try:
                                                if '_RNA_UI' not in obj:
                                                    obj['_RNA_UI'] = {}
                                                obj[key] = value
                                                obj['_RNA_UI'][key] = {
                                                    "description": "",
                                                    "default": value,
                                                    "is_overridable_library": True
                                                }
                                                self.report({'INFO'}, f"Set property {key}={value} on {obj.name}")
                                            except Exception as e:
                                                self.report({'WARNING'}, f"Failed to set {key} on {obj.name}: {str(e)}")
                    except Exception as e:
                        self.report({'WARNING'}, f"Error applying properties: {str(e)}")
                    
                    for obj in new_objects:
                        obj.update_tag()
                        if context.screen and context.screen.areas:
                            for area in context.screen.areas:
                                area.tag_redraw()
            else:
                self.report({'ERROR'}, "No .glb file found in the NX3 archive.")
                return {'CANCELLED'}

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    Export Operator
# ------------------------------------------------------------------------
class ExportNX3(bpy.types.Operator, ExportHelper):
    """Export selected objects to .nx3 (zip of .glb, .txt, .safetensor),
    with options to apply modifiers and combine meshes."""
    bl_idname = "export_scene.nx3"
    bl_label = "Export NX3"
    bl_options = {'UNDO'}

    filename_ext = ".nx3"
    filter_glob: StringProperty(
        default="*.nx3",
        options={'HIDDEN'},
        maxlen=255,
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        default=True,
        description="Apply all modifiers on selected objects before exporting"
    )
    combine_meshes: BoolProperty(
        name="Combine Meshes",
        default=True,
        description="Combine all selected meshes into one mesh"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "apply_modifiers")
        layout.prop(self, "combine_meshes")

    def get_custom_properties(self, obj):
        """Extract custom properties from an object."""
        props = {}
        if obj and hasattr(obj, 'keys'):
            for key in obj.keys():
                if key != '_RNA_UI':
                    props[key] = obj[key]
        return props

    def execute(self, context):
        # Ensure final export path ends with ".nx3"
        export_path = self.filepath
        if not export_path.lower().endswith(".nx3"):
            export_path += ".nx3"

        if os.path.exists(export_path):
            try:
                os.remove(export_path)
            except PermissionError:
                self.report({'ERROR'}, f"Cannot overwrite existing file: {export_path}. File may be in use.")
                return {'CANCELLED'}
            except Exception as e:
                self.report({'ERROR'}, f"Error removing existing file: {str(e)}")
                return {'CANCELLED'}

        base_filename = os.path.splitext(os.path.basename(export_path))[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            original_selection = context.selected_objects
            if not original_selection:
                self.report({'ERROR'}, "No objects selected for export.")
                return {'CANCELLED'}

            bpy.ops.object.select_all(action='DESELECT')
            duplicated_object_names = []

            # Duplicate each selected object
            for obj in original_selection:
                new_obj = obj.copy()
                if obj.data:
                    new_obj.data = obj.data.copy()
                context.collection.objects.link(new_obj)

                new_obj.select_set(True)
                context.view_layer.objects.active = new_obj

                if new_obj.type == 'MESH' and self.apply_modifiers:
                    for mod in new_obj.modifiers:
                        bpy.ops.object.modifier_apply(modifier=mod.name)

                new_obj.select_set(False)
                duplicated_object_names.append(new_obj.name)

            # Combine meshes if requested
            if self.combine_meshes:
                mesh_names = [
                    name for name in duplicated_object_names
                    if bpy.data.objects[name].type == 'MESH'
                ]
                if mesh_names:
                    bpy.ops.object.select_all(action='DESELECT')
                    for m_name in mesh_names:
                        if m_name in bpy.data.objects:
                            bpy.data.objects[m_name].select_set(True)
                    context.view_layer.objects.active = bpy.data.objects[mesh_names[0]]
                    bpy.ops.object.join()

                    single_merged_name = mesh_names[0]
                    merged_obj = bpy.data.objects[single_merged_name]
                    merged_obj.name = base_filename

                    for other_name in mesh_names[1:]:
                        if other_name in bpy.data.objects:
                            bpy.data.objects.remove(bpy.data.objects[other_name], do_unlink=True)

                    updated_list = []
                    for d_name in duplicated_object_names:
                        if d_name in mesh_names[1:]:
                            continue
                        if d_name == mesh_names[0]:
                            updated_list.append(merged_obj.name)
                        else:
                            updated_list.append(d_name)
                    duplicated_object_names = updated_list

                    bpy.ops.object.select_all(action='DESELECT')
                    merged_obj.select_set(True)
                    context.view_layer.objects.active = merged_obj

                else:
                    self.report({'WARNING'}, "No MESH objects to combine.")
                    bpy.ops.object.select_all(action='DESELECT')
                    for d_name in duplicated_object_names:
                        if d_name in bpy.data.objects:
                            bpy.data.objects[d_name].select_set(True)
                    if duplicated_object_names:
                        active_name = duplicated_object_names[0]
                        if active_name in bpy.data.objects:
                            context.view_layer.objects.active = bpy.data.objects[active_name]
            else:
                bpy.ops.object.select_all(action='DESELECT')
                for d_name in duplicated_object_names:
                    if d_name in bpy.data.objects:
                        bpy.data.objects[d_name].select_set(True)
                if duplicated_object_names:
                    active_name = duplicated_object_names[0]
                    if active_name in bpy.data.objects:
                        context.view_layer.objects.active = bpy.data.objects[active_name]

            glb_filename = os.path.join(temp_dir, "model.glb")
            bpy.ops.export_scene.gltf(
                filepath=glb_filename,
                export_format='GLB',
                use_selection=True,
            )

            # Prepare properties for export
            properties = {}
            if self.combine_meshes and context.selected_objects:
                last_selected = context.selected_objects[-1]
                properties = self.get_custom_properties(last_selected)
            else:
                properties = {}
                for obj in context.selected_objects:
                    obj_props = self.get_custom_properties(obj)
                    if obj_props:
                        properties[obj.name] = obj_props

            # Write properties to nx3.json in JSON format
            json_filename = os.path.join(temp_dir, "nx3.json")
            
            # Create structured JSON with additional metadata
            json_data = {
                "version": "1.0",
                "type": "nx3_properties",
                "Geometry_properties": {
                    "name": base_filename,
                    "collection": "Collection",
                    "3d_format": "glb"
                },
                "Lora_properties": {
                    "Lora_source": "local",
                    "Lora_destination": ""
                },
                "properties": properties
            }
            
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=4, default=lambda o: str(o))
            
            safetensor_filename = os.path.join(temp_dir, "nx3.safetensor")
            with open(safetensor_filename, "wb") as f:
                f.write(b"")

            zip_filename = os.path.join(temp_dir, "temp_export.zip")
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as z:
                z.write(glb_filename, arcname="model.glb")
                z.write(json_filename, arcname="nx3.json")
                z.write(safetensor_filename, arcname="nx3.safetensor")

            try:
                shutil.move(zip_filename, export_path)
            except (PermissionError, OSError) as e:
                self.report({'ERROR'}, f"Failed to save file: {str(e)}")
                return {'CANCELLED'}

            for d_name in duplicated_object_names:
                if d_name in bpy.data.objects:
                    bpy.data.objects.remove(bpy.data.objects[d_name], do_unlink=True)

        self.report({'INFO'}, f"Exported NX3 to: {export_path}")
        return {'FINISHED'}


# -------------------------------------------------
# Registration
# -------------------------------------------------
def menu_func_import(self, context):
    self.layout.operator(ImportNX3.bl_idname, text="Neural x 3D object (.nx3)")

def menu_func_export(self, context):
    self.layout.operator(ExportNX3.bl_idname, text="Neural x 3D object (.nx3)")

def register():
    bpy.utils.register_class(ImportNX3)
    bpy.utils.register_class(ExportNX3)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(ImportNX3)
    bpy.utils.unregister_class(ExportNX3)

if __name__ == "__main__":
    register()
