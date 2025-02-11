bl_info = {
    "name": "NX3 Importer/Exporter",
    "author": "IRLABS",
    "version": (1, 3),
    "blender": (4, 2, 0),
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
                    # Try to convert to float/int if it looks like a number
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        # Keep as string if conversion fails
                        pass
                
                # Create or update the custom property
                if key not in obj:
                    obj[key] = value
                else:
                    del obj[key]  # Delete existing property first
                    obj[key] = value  # Then recreate it
                    
                # Ensure the property is visible in the UI
                if '_RNA_UI' not in obj:
                    obj['_RNA_UI'] = {}
                if key not in obj['_RNA_UI']:
                    obj['_RNA_UI'][key] = {"description": ""}
                    
            except Exception as e:
                print(f"Failed to set property {key}: {str(e)}")

    def execute(self, context):
        nx3_path = self.filepath

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with zipfile.ZipFile(nx3_path, 'r') as zfile:
                    zfile.extractall(temp_dir)
            except zipfile.BadZipFile:
                self.report({'ERROR'}, "Invalid .nx3 file (cannot unzip).")
                return {'CANCELLED'}

            # Find glb, text, and safetensor
            glb_path, txt_path, safetensor_path = None, None, None
            for filename in os.listdir(temp_dir):
                lower_name = filename.lower()
                file_path = os.path.join(temp_dir, filename)

                if lower_name.endswith(".glb"):
                    glb_path = file_path
                elif lower_name.endswith(".txt"):
                    txt_path = file_path
                elif lower_name.endswith(".safetensor"):
                    safetensor_path = file_path

            # First load the properties from txt file if it exists
            properties_data = None
            if txt_path and os.path.isfile(txt_path):
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict) and "properties" in data:
                        properties_data = data["properties"]
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to load properties: {str(e)}")

            # Store the number of objects before import
            initial_objects = set(obj.name for obj in bpy.data.objects)

            # Import glb if found
            if glb_path and os.path.isfile(glb_path):
                bpy.ops.import_scene.gltf(filepath=glb_path)
                
                # Get newly imported objects
                new_objects = [obj for obj in bpy.data.objects if obj.name not in initial_objects]
                
                # Apply properties if we have them
                if properties_data and new_objects:
                    try:
                        if isinstance(properties_data, dict):
                            # Check if we have a nested dictionary (multiple objects case)
                            has_nested_dicts = any(isinstance(v, dict) for v in properties_data.values())
                            
                            if has_nested_dicts:
                                # Multiple objects case - match by name
                                self.report({'INFO'}, "Found multiple property sets")
                                for obj in new_objects:
                                    # Try different name variations to match properties
                                    obj_name = obj.name
                                    base_name = obj_name.split('.')[0]  # Remove .001 etc
                                    
                                    # Try exact match first, then base name
                                    if obj_name in properties_data:
                                        prop_set = properties_data[obj_name]
                                    elif base_name in properties_data:
                                        prop_set = properties_data[base_name]
                                    else:
                                        continue  # No matching properties found for this object
                                    
                                    # Apply the properties
                                    for key, value in prop_set.items():
                                        try:
                                            # Create the RNA UI dict if it doesn't exist
                                            if '_RNA_UI' not in obj:
                                                obj['_RNA_UI'] = {}
                                            
                                            # Set the property
                                            obj[key] = value
                                            
                                            # Update the UI
                                            obj['_RNA_UI'][key] = {
                                                "description": "",
                                                "default": value,
                                                "is_overridable_library": True
                                            }
                                            
                                            self.report({'INFO'}, f"Set property {key}={value} on {obj.name}")
                                        except Exception as e:
                                            self.report({'WARNING'}, f"Failed to set {key} on {obj.name}: {str(e)}")
                            else:
                                # Single property set case - apply to all objects
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
                    
                    # Force update the UI
                    for obj in new_objects:
                        obj.update_tag()
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
                if key != '_RNA_UI':  # Skip RNA UI property
                    props[key] = obj[key]
        return props

    def execute(self, context):
        # Ensure final export path ends with ".nx3"
        export_path = self.filepath
        if not export_path.lower().endswith(".nx3"):
            export_path += ".nx3"

        # Check if file exists and try to remove it first
        if os.path.exists(export_path):
            try:
                os.remove(export_path)
            except PermissionError:
                self.report({'ERROR'}, f"Cannot overwrite existing file: {export_path}. File may be in use.")
                return {'CANCELLED'}
            except Exception as e:
                self.report({'ERROR'}, f"Error removing existing file: {str(e)}")
                return {'CANCELLED'}

        # We'll name the combined mesh after the file's base name
        base_filename = os.path.splitext(os.path.basename(export_path))[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            original_selection = context.selected_objects
            if not original_selection:
                self.report({'ERROR'}, "No objects selected for export.")
                return {'CANCELLED'}

            # Deselect everything for safety
            bpy.ops.object.select_all(action='DESELECT')

            # We'll store only the names of the duplicated objects
            duplicated_object_names = []

            # ----------------------------------------------------------------
            # 1) Duplicate each selected object, applying modifiers if needed
            # ----------------------------------------------------------------
            for obj in original_selection:
                # Duplicate object
                new_obj = obj.copy()
                if obj.data:
                    new_obj.data = obj.data.copy()

                context.collection.objects.link(new_obj)

                # Temporarily select/activate new_obj to apply modifiers
                new_obj.select_set(True)
                context.view_layer.objects.active = new_obj

                if new_obj.type == 'MESH' and self.apply_modifiers:
                    for mod in new_obj.modifiers:
                        bpy.ops.object.modifier_apply(modifier=mod.name)

                # Deselect for the next iteration
                new_obj.select_set(False)

                # Store this object's name
                duplicated_object_names.append(new_obj.name)

            # ----------------------------------------------------------------
            # 2) If combine_meshes is True, join all MESH duplicates into one
            # ----------------------------------------------------------------
            if self.combine_meshes:
                # Gather mesh objects by name
                mesh_names = [
                    name for name in duplicated_object_names
                    if bpy.data.objects[name].type == 'MESH'
                ]
                if mesh_names:
                    # Deselect everything
                    bpy.ops.object.select_all(action='DESELECT')

                    # Select only the mesh objects
                    for m_name in mesh_names:
                        if m_name in bpy.data.objects:
                            bpy.data.objects[m_name].select_set(True)
                    context.view_layer.objects.active = bpy.data.objects[mesh_names[0]]

                    # Join them into the first mesh
                    bpy.ops.object.join()

                    single_merged_name = mesh_names[0]
                    merged_obj = bpy.data.objects[single_merged_name]
                    merged_obj.name = base_filename  # rename after join

                    # Remove the others from the scene
                    for other_name in mesh_names[1:]:
                        if other_name in bpy.data.objects:
                            bpy.data.objects.remove(bpy.data.objects[other_name], do_unlink=True)

                    # Update duplicated_object_names:
                    # Only keep the merged_obj plus any non-mesh objects
                    updated_list = []
                    for d_name in duplicated_object_names:
                        # If it's one of the "other" meshes, skip
                        if d_name in mesh_names[1:]:
                            continue
                        # If it's the survivor, use the new name
                        if d_name == mesh_names[0]:
                            updated_list.append(merged_obj.name)  # new name
                        else:
                            updated_list.append(d_name)
                    duplicated_object_names = updated_list

                    # Re-select just the merged object
                    bpy.ops.object.select_all(action='DESELECT')
                    merged_obj.select_set(True)
                    context.view_layer.objects.active = merged_obj

                else:
                    self.report({'WARNING'}, "No MESH objects to combine.")
                    # If no mesh objects exist, just select all duplicates for export
                    bpy.ops.object.select_all(action='DESELECT')
                    for d_name in duplicated_object_names:
                        if d_name in bpy.data.objects:
                            bpy.data.objects[d_name].select_set(True)
                    if duplicated_object_names:
                        active_name = duplicated_object_names[0]
                        if active_name in bpy.data.objects:
                            context.view_layer.objects.active = bpy.data.objects[active_name]

            else:
                # combine_meshes OFF: select all duplicated objects for export
                bpy.ops.object.select_all(action='DESELECT')
                for d_name in duplicated_object_names:
                    if d_name in bpy.data.objects:
                        bpy.data.objects[d_name].select_set(True)
                if duplicated_object_names:
                    active_name = duplicated_object_names[0]
                    if active_name in bpy.data.objects:
                        context.view_layer.objects.active = bpy.data.objects[active_name]

            # ----------------------------------------------------------------
            # 3) Export the selection to GLB
            # ----------------------------------------------------------------
            glb_filename = os.path.join(temp_dir, "model.glb")
            bpy.ops.export_scene.gltf(
                filepath=glb_filename,
                export_format='GLB',
                use_selection=True,
            )

            # ----------------------------------------------------------------
            # 4) Create nx3.txt and nx3.safetensor
            # ----------------------------------------------------------------
            # Get properties from the appropriate object
            properties = {}
            if self.combine_meshes and context.selected_objects:
                # Use properties from the last selected object when combining
                last_selected = context.selected_objects[-1]
                properties = self.get_custom_properties(last_selected)
            else:
                # If not combining, gather properties from all objects
                properties = {}
                for obj in context.selected_objects:
                    obj_props = self.get_custom_properties(obj)
                    if obj_props:  # Only add if there are properties
                        properties[obj.name] = obj_props

            # Write properties to txt file in JSON format
            txt_filename = os.path.join(temp_dir, "nx3.txt")
            with open(txt_filename, "w", encoding="utf-8") as f:
                json.dump({
                    "version": "1.0",
                    "type": "nx3_properties",
                    "properties": properties
                }, f, indent=4)

            safetensor_filename = os.path.join(temp_dir, "nx3.safetensor")
            with open(safetensor_filename, "wb") as f:
                f.write(b"")

            # ----------------------------------------------------------------
            # 5) Zip them up and rename to .nx3
            # ----------------------------------------------------------------
            zip_filename = os.path.join(temp_dir, "temp_export.zip")
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as z:
                z.write(glb_filename, arcname="model.glb")
                z.write(txt_filename, arcname="nx3.txt")
                z.write(safetensor_filename, arcname="nx3.safetensor")

            # Update the file move operation with error handling
            try:
                shutil.move(zip_filename, export_path)
            except (PermissionError, OSError) as e:
                self.report({'ERROR'}, f"Failed to save file: {str(e)}")
                return {'CANCELLED'}

            # ----------------------------------------------------------------
            # 6) Final Cleanup: Remove duplicates by name
            # ----------------------------------------------------------------
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
