# NX3: Neural eXchange 3D
![NX3 Icon](https://github.com/pristinaai/nx3/blob/main/nx3-icon.jpg?raw=true)

**NX3** is a lightweight, extensible file format for sharing 3D models alongside additional neural data. An NX3 file is simply a `.zip` archive renamed with the `.nx3` extension. By convention, inside the archive you will find:
1. A **`.glb`** file containing the 3D model (using the [glTF 2.0](https://github.com/KhronosGroup/glTF) binary format).
2. A **`.txt`** file for storing human-readable metadata or notes.
3. A **`.safetensor`** file for optional neural data, weights, or anything relevant to advanced ML/AI workflows.

This layout makes NX3 simple to inspect, extract, and repack using standard zip tools—but also seamlessly integrable within pipelines that require a consistent 3D and neural data packaging format.

---

## Why NX3?

- **Single, self-contained package**: Keep your geometry, metadata, and ML/AI artifacts together.  
- **Built on open standards**: The 3D model is in `.glb` (binary glTF), which is widely supported by engines, tools, and converters.  
- **Extensible**: The `.txt` and `.safetensor` files can contain anything you like, from user instructions to advanced model weights—no format policing.  
- **Easy to create and open**: Zip your files, rename to `.nx3`, and you’re done. Tools that understand NX3 can parse it automatically.

---

## Blender Integration

### Blender Add-on

A dedicated Blender add-on is available to:

1. **Import NX3**: Extracts the `.glb` from your NX3 and imports it into Blender.  
2. **Export NX3**: Exports selected objects in Blender as `.glb`, adds placeholder `.txt` and `.safetensor` files (or your own data), zips them, and renames the result to `.nx3`.

**Features**:
- **Apply modifiers** at export (optional).  
- **Combine Meshes** at export (optional).  
- **Automatic naming** of the combined mesh and final `.nx3` file.  

### Installation

1. Download the add-on Python script (e.g. `nx3_import_export.py`).
2. In Blender, open **Edit > Preferences**.
3. Go to **Add-ons** and click **Install**.
4. Select the `.py` script.
5. Enable the new add-on in the list. You should see:
   - **File > Import > NX3 (.nx3)**
   - **File > Export > NX3 (.nx3)**

### Usage

- **Import**:  
  1. Go to **File > Import > NX3 (.nx3)**.  
  2. Choose your `.nx3` file.  
  3. The add-on extracts and imports the `.glb` and logs any `.txt` or `.safetensor` found.

- **Export**:  
  1. Select the objects in your scene.  
  2. Go to **File > Export > NX3 (.nx3)**.  
  3. Choose your export path.  
  4. (Optional) Toggle “Apply Modifiers” or “Combine Meshes.”  
  5. Click “Export NX3.”  
  6. Blender creates a `.glb`, `.txt`, `.safetensor`, zips them, and renames the file to `.nx3`.

---

## Working with NX3 Files Directly

Because `.nx3` is just a **renamed zip**:
- **To open**: Rename `.nx3` to `.zip`, then uncompress. You’ll see `model.glb`, `nx3.txt`, and `nx3.safetensor` (names may vary).
- **To pack**: Place your `.glb`, `.txt`, and `.safetensor` in a folder. Zip them and rename the `.zip` to `.nx3`.

---

## Contributing

Feel free to submit pull requests or raise issues to:
- Improve the Blender add-on.
- Suggest new best practices for storing metadata or neural data.
- Share additional scripts or tools for working with NX3 files.

---

## License

This project is distributed under the [MIT License](./LICENSE) (or whichever license your repository uses). Please check the repository’s [license file](./LICENSE) for details.

---

## Links & References
- [glTF 2.0 Specification](https://github.com/KhronosGroup/glTF)
- [SafeTensor Format](https://github.com/huggingface/safetensors)
- [PristinaAI / nx3 GitHub](https://github.com/pristinaai/nx3)
