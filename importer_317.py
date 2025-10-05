# importer_317.py
import bpy
import struct
import os
import colorsys
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, CollectionProperty
from bpy.types import Operator, OperatorFileListElement
from mathutils import Vector
# =============================================================================
# PROPERTY GROUPS FOR PMN (from merged)
# =============================================================================
class RS_Material_PropertyGroup(bpy.types.PropertyGroup):
    p: bpy.props.FloatVectorProperty(name="P", subtype='TRANSLATION', default=(0.0, 0.0, 0.0))
    m: bpy.props.FloatVectorProperty(name="M", subtype='TRANSLATION', default=(0.0, 0.0, 0.0))
    n: bpy.props.FloatVectorProperty(name="N", subtype='TRANSLATION', default=(0.0, 0.0, 0.0))
    offset_u: bpy.props.FloatProperty(name="Offset U", default=0.0)
    offset_v: bpy.props.FloatProperty(name="Offset V", default=0.0)
    scale_u: bpy.props.FloatProperty(name="Scale U", default=1.0)
    scale_v: bpy.props.FloatProperty(name="Scale V", default=1.0)
# =============================================================================
# DATA STREAM (updated with signed_byte and fixed smart_int)
# =============================================================================
class DataStream:
    def __init__(self, data):
        self.data = data
        self.offset = 0
   
    def read_byte(self):
        if self.offset >= len(self.data):
            return 0
        byte = self.data[self.offset]
        self.offset += 1
        return byte
   
    def read_signed_byte(self):
        if self.offset >= len(self.data):
            return 0
        byte = self.data[self.offset]
        self.offset += 1
        if byte > 127:
            byte -= 256
        return byte
   
    def read_unsigned_short(self):
        if self.offset + 1 >= len(self.data):
            return 0
        value = struct.unpack('>H', self.data[self.offset:self.offset+2])[0]
        self.offset += 2
        return value
   
    def unpack_smart_int(self):
        byte1 = self.read_byte()
        if (byte1 & 0x80) == 0:
            return byte1 - 64
        else:
            byte2 = self.read_byte()
            value = ((byte1 & 0x7F) << 8) | byte2
            return value - 16384
       
    def remaining(self):
        return len(self.data) - self.offset
   
    def set_position(self, pos):
        self.offset = pos
# =============================================================================
# HELPER FUNCTIONS (updated from merged)
# =============================================================================
def to_signed_byte(value):
    """Convert unsigned byte to signed byte"""
    value %= 256
    if value > 127:
        value -= 256
    return value
def get_texture_dump_path():
    """Finds the texture_dump folder relative to the script location"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "texture_dump")
    if os.path.exists(path):
        print(f"Found texture dump path: {path}")
        return path
    print(f"Warning: Could not find texture_dump in script directory: {path}")
    return ""
def find_texture_file(texture_id):
    """Finds the first matching texture file for a given ID"""
    base_path = get_texture_dump_path()
    texture_dirs = [
        base_path,
        os.path.join(base_path, "317TEX")
    ]
    patterns = [str(texture_id), f"texture_{texture_id}", f"tex_{texture_id}"]
    supported_exts = ('.png', '.jpg', '.jpeg', '.tga', '.bmp')
    for tex_dir in texture_dirs:
        if not os.path.isdir(tex_dir):
            continue
        for filename in os.listdir(tex_dir):
            fn_lower = filename.lower()
            name_part, ext_part = os.path.splitext(fn_lower)
            if ext_part in supported_exts:
                for pattern in patterns:
                    if name_part == pattern.lower():
                        print(f"Found texture {texture_id}: {filename}")
                        return os.path.join(tex_dir, filename)
    print(f"Texture {texture_id} not found")
    return None
def setup_material_alpha(mat, alpha_byte):
    """Configures a material for alpha blending."""
    if not mat or not mat.use_nodes:
        return
   
    alpha_float = (255 - alpha_byte) / 255.0
   
    mat.blend_method = 'BLEND'
    if hasattr(mat, 'shadow_method'):
        mat.shadow_method = 'CLIP'
   
    bsdf_node = mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf_node:
        bsdf_node = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
   
    if bsdf_node:
        bsdf_node.inputs['Alpha'].default_value = alpha_float
def create_placeholder_texture(tex_node, texture_id):
    """Create placeholder texture for missing files"""
    img_name = f"Missing_Tex_{texture_id}"
    existing_img = bpy.data.images.get(img_name)
    if existing_img:
        tex_node.image = existing_img
        return
    size = 128
    img = bpy.data.images.new(img_name, width=size, height=size)
    pixels = []
    for y in range(size):
        for x in range(size):
            checker = ((x // 16) + (y // 16)) % 2
            if checker:
                r = (texture_id % 256) / 255.0
                g = ((texture_id // 256) % 256) / 255.0
                b = 1.0
            else:
                r, g, b = 0.2, 0.2, 0.2
            pixels.extend([r, g, b, 1.0])
    img.pixels = pixels
    tex_node.image = img
def rune_hsl_to_rgb(hsl_value):
    """Convert RuneScape HSL to RGB"""
    if hsl_value == 0:
        return (0.5, 0.5, 0.5)
    h_val = (hsl_value >> 10) & 0x3F
    s_val = (hsl_value >> 7) & 0x07
    l_val = hsl_value & 0x7F
    h = h_val / 63.0
    s = s_val / 7.0
    v = l_val / 127.0
    if s < 1e-6:
        return (v, v, v)
    return colorsys.hsv_to_rgb(h, s, v)
def create_material_from_hsl(hsl_value):
    """Create a Blender material from HSL color value"""
    rgb = rune_hsl_to_rgb(hsl_value)
    mat = bpy.data.materials.new(name=f"RS_Color_{hsl_value}")
    mat.use_nodes = True
    bsdf_node = mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf_node:
        mat.node_tree.nodes.clear()
        output_node = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        bsdf_node = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        bsdf_node.name = "Principled BSDF"
        mat.node_tree.links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
        bsdf_node.location = (0, 0)
        output_node.location = (200, 0)
    bsdf_node.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf_node.inputs['Roughness'].default_value = 1.0
    if 'Specular' in bsdf_node.inputs: # Older Blender versions
        bsdf_node.inputs['Specular'].default_value = 0.0
    else: # Newer Blender versions (Specular is a socket)
        bsdf_node.inputs['Specular IOR Level'].default_value = 0.0
    return mat
def create_texture_material(texture_id):
    """Create a Blender material with a simplified texture node setup"""
    mat_name = f"Texture_{texture_id}"
    mat = bpy.data.materials.get(mat_name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
   
    # --- Create Nodes ---
    output_node = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    bsdf_node = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf_node.name = "Principled BSDF"
    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex_coord_node = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    mapping_node = mat.node_tree.nodes.new('ShaderNodeMapping')
    mapping_node.name = 'RS Mapping'
   
    tex_node.extension = 'REPEAT'
   
    # --- Load Texture Image ---
    tex_path = find_texture_file(texture_id)
    if tex_path:
        try:
            tex_node.image = bpy.data.images.load(tex_path, check_existing=True)
            print(f" > Loaded texture: {os.path.basename(tex_path)}")
        except Exception as e:
            print(f" > Failed to load texture {tex_path}: {e}")
            create_placeholder_texture(tex_node, texture_id)
    else:
        create_placeholder_texture(tex_node, texture_id)
   
    # --- Configure BSDF ---
    bsdf_node.inputs['Roughness'].default_value = 1.0
    if 'Specular' in bsdf_node.inputs:
        bsdf_node.inputs['Specular'].default_value = 0.0
    else:
        bsdf_node.inputs['Specular IOR Level'].default_value = 0.0
       
    # --- Link Nodes ---
    mat.node_tree.links.new(tex_coord_node.outputs['UV'], mapping_node.inputs['Vector'])
    mat.node_tree.links.new(mapping_node.outputs['Vector'], tex_node.inputs['Vector'])
    mat.node_tree.links.new(tex_node.outputs['Color'], bsdf_node.inputs['Base Color']) # Direct link
    mat.node_tree.links.new(tex_node.outputs['Alpha'], bsdf_node.inputs['Alpha'])
    mat.node_tree.links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
   
    # --- Node Positions for Readability ---
    tex_coord_node.location = (-700, 0)
    mapping_node.location = (-500, 0)
    tex_node.location = (-300, 0)
    bsdf_node.location = (0, 0)
    output_node.location = (250, 0)
   
    return mat
def compute_uv_from_pmn(vert, p, m, n):
    """Computes UV coordinates for a vertex based on PMN basis"""
    f1 = m - p
    f2 = n - p
    det = f1.dot(f1) * f2.dot(f2) - f1.dot(f2)**2
    if abs(det) < 1e-9:
        return 0.0, 0.0
   
    inv_det = 1.0 / det
    inv00 = f2.dot(f2) * inv_det
    inv01 = -f1.dot(f2) * inv_det
    inv10 = -f1.dot(f2) * inv_det
    inv11 = f1.dot(f1) * inv_det
   
    d = vert - p
    u = inv00 * d.dot(f1) + inv01 * d.dot(f2)
    v = inv10 * d.dot(f1) + inv11 * d.dot(f2)
    return u, v
# =============================================================================
# 317/OSRS IMPORT 
# =============================================================================
def import_old_format(data, filepath):
    """Import 317/OSRS format models (decode1)"""
    print(" > Importing 317/OSRS format model...")
    if len(data) < 18:
        print("ERROR: File too small for 317/OSRS format.")
        return {'CANCELLED'}
   
    footer_data = data[-18:]
    (num_vertices, num_faces, num_tex_triangles,
     textured_flag, pri_flag, alpha_flag, tskin_flag, vskin_flag,
     x_data_len, y_data_len, z_data_len, face_indices_len) = struct.unpack('>HHBBBBBBHHHH', footer_data)
    # --- Calculate Offsets (Logic from codex.txt) ---
    pos = 0
    vert_dirs_offset = pos; pos += num_vertices
    face_types_offset = pos; pos += num_faces
    face_priorities_offset = pos
    if pri_flag == 255: pos += num_faces
    face_tskins_offset = pos
    if tskin_flag == 1: pos += num_faces
    face_textures_offset = pos # Corresponds to face types in unversioned skeletal
    if textured_flag == 1: pos += num_faces
    vertex_skins_offset = pos
    if vskin_flag == 1: pos += num_vertices
    alpha_data_offset = pos
    if alpha_flag == 1: pos += num_faces
    face_indices_offset = pos; pos += face_indices_len
    face_colors_offset = pos; pos += num_faces * 2
    texture_coords_offset = pos
    if textured_flag == 1: pos += num_tex_triangles * 6
    x_data_offset = pos; pos += x_data_len
    y_data_offset = pos; pos += y_data_len
    z_data_offset = pos
   
    # Read data sections using calculated offsets
    vert_dirs_data = data[vert_dirs_offset:vert_dirs_offset + num_vertices]
    face_types_data = data[face_types_offset:face_types_offset + num_faces]
    face_priorities_data = data[face_priorities_offset:face_priorities_offset + num_faces] if pri_flag == 255 else b''
    face_tskins_data = data[face_tskins_offset:face_tskins_offset + num_faces] if tskin_flag == 1 else b''
    face_textures_data = data[face_textures_offset:face_textures_offset + num_faces] if textured_flag == 1 else b''
    vertex_skins_data = data[vertex_skins_offset:vertex_skins_offset + num_vertices] if vskin_flag == 1 else b''
    alpha_data = data[alpha_data_offset:alpha_data_offset + num_faces] if alpha_flag == 1 else b''
    face_indices_data = data[face_indices_offset:face_indices_offset + face_indices_len]
    face_colors_data = data[face_colors_offset:face_colors_offset + num_faces * 2]
    texture_coords_data = data[texture_coords_offset:texture_coords_offset + num_tex_triangles * 6] if textured_flag == 1 else b''
    x_data = data[x_data_offset:x_data_offset + x_data_len]
    y_data = data[y_data_offset:y_data_offset + y_data_len]
    z_data = data[z_data_offset:] # To the end
   
    # --- Unpack Vertices ---
    vertices = []
    last_x, last_y, last_z = 0, 0, 0
    x_stream = DataStream(x_data); y_stream = DataStream(y_data); z_stream = DataStream(z_data)
    for i in range(num_vertices):
        flag = vert_dirs_data[i]
        dx, dy, dz = 0, 0, 0
        if flag & 1: dx = x_stream.unpack_smart_int()
        if flag & 2: dy = y_stream.unpack_smart_int()
        if flag & 4: dz = z_stream.unpack_smart_int()
        last_x += dx; last_y += dy; last_z += dz
        vertices.append((last_x, last_z, -last_y))
    # --- Unpack Faces ---
    faces = []
    v1, v2, v3 = 0, 0, 0
    indices_stream = DataStream(face_indices_data)
    compress_stream = DataStream(face_types_data) # This is the compress type stream in this format
    offset = 0
    for i in range(num_faces):
        opcode = compress_stream.read_byte()
        if opcode == 1:
            v1 = indices_stream.unpack_smart_int() + offset; offset = v1
            v2 = indices_stream.unpack_smart_int() + offset; offset = v2
            v3 = indices_stream.unpack_smart_int() + offset; offset = v3
        elif opcode == 2:
            v2 = v3
            v3 = indices_stream.unpack_smart_int() + offset; offset = v3
        elif opcode == 3:
            v1 = v3
            v3 = indices_stream.unpack_smart_int() + offset; offset = v3
        elif opcode == 4:
            tmp = v1; v1 = v2; v2 = tmp
            v3 = indices_stream.unpack_smart_int() + offset; offset = v3
       
        v1 = max(0, min(v1, num_vertices-1)); v2 = max(0, min(v2, num_vertices-1)); v3 = max(0, min(v3, num_vertices-1))
        faces.append((v1, v2, v3))
   
    # --- Process Face Data ---
    face_colors = list(struct.unpack(f'>{num_faces}H', face_colors_data))
    face_texture_ids = [-1] * num_faces
    texture_coordinate_indices = [-1] * num_faces
    if textured_flag == 1:
        for i in range(num_faces):
            flag = face_textures_data[i]
            if flag & 2 == 2: # Is textured
                face_texture_ids[i] = face_colors[i]
                texture_coordinate_indices[i] = flag >> 2
   
    # --- Unpack Texture Triangles (PMN) ---
    texture_triangles = []
    if textured_flag == 1 and texture_coords_data:
        tex_stream = DataStream(texture_coords_data)
        for _ in range(num_tex_triangles):
            p = tex_stream.read_unsigned_short(); m = tex_stream.read_unsigned_short(); n = tex_stream.read_unsigned_short()
            texture_triangles.append((p, m, n))
    has_priorities_to_process = (pri_flag == 255)
   
    return create_mesh_with_uvs(
        vertices, faces, face_colors, face_texture_ids, texture_coordinate_indices, texture_triangles, filepath,
        face_priorities_data, face_tskins_data, vertex_skins_data, alpha_data,
        has_priorities_to_process, tskin_flag == 1, vskin_flag == 1, num_faces, num_vertices
    )
# =============================================================================
# MESH CREATION (from merged create_mesh_with_uvs and create_rs_data_layers)
# =============================================================================
def create_mesh_with_uvs(vertices, faces, face_colors, face_texture_ids,
                         texture_coordinate_indices, texture_triangles, filepath,
                         face_priorities_data, face_tskins_data, vertex_skins_data, face_alphas_data,
                         has_priorities, has_tskins, has_vskins, triangle_count, vertex_count):
    """Create mesh with proper UV mapping using PMN method"""
    model_name = os.path.splitext(os.path.basename(filepath))[0]
    mesh = bpy.data.meshes.new(name=f"{model_name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name=model_name, object_data=mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
   
    face_alphas = list(face_alphas_data) if face_alphas_data else [255] * triangle_count
    # Create materials
    material_map = {}
    for i in range(min(triangle_count, len(faces))):
        alpha_val = face_alphas[i] if i < len(face_alphas) else 255
        tex_id = face_texture_ids[i] if i < len(face_texture_ids) else -1
       
        if tex_id != -1:
            mat_key = ('tex', tex_id, alpha_val)
            if mat_key not in material_map:
                mat = create_texture_material(tex_id)
                if alpha_val < 255:
                    setup_material_alpha(mat, alpha_val)
                material_map[mat_key] = mat
        else:
            hsl = face_colors[i] if i < len(face_colors) else 0
            mat_key = ('color', hsl, alpha_val)
            if mat_key not in material_map:
                mat = create_material_from_hsl(hsl)
                if alpha_val < 255:
                    setup_material_alpha(mat, alpha_val)
                material_map[mat_key] = mat
    # Append materials to object and assign indices
    obj_mats = list(material_map.values())
    for mat in obj_mats:
        obj.data.materials.append(mat)
   
    mat_to_idx = {mat.name: i for i, mat in enumerate(obj.data.materials)}
    if mesh.polygons:
        for i, poly in enumerate(mesh.polygons):
            alpha_val = face_alphas[i] if i < len(face_alphas) else 255
            tex_id = face_texture_ids[i] if i < len(face_texture_ids) else -1
            if tex_id != -1:
                mat_key = ('tex', tex_id, alpha_val)
            else:
                hsl = face_colors[i] if i < len(face_colors) else 0
                mat_key = ('color', hsl, alpha_val)
           
            mat = material_map.get(mat_key)
            if mat:
                poly.material_index = mat_to_idx.get(mat.name, 0)
   
    # Create overlay color vertex layer (Note: This is no longer used by the shader but is preserved as data)
    color_layer = mesh.vertex_colors.new(name="RSCOLOR")
    for i, poly in enumerate(mesh.polygons):
        if i < len(face_texture_ids) and face_texture_ids[i] != -1:
            hsl = face_colors[i]
            rgb = rune_hsl_to_rgb(hsl)
            col = (*rgb, 1.0)
        else:
            col = (1.0, 1.0, 1.0, 1.0)
        for loop_index in poly.loop_indices:
            color_layer.data[loop_index].color = col

    # Create UV Map only if there are textured faces
    has_textured_faces = any(face_texture_ids[i] != -1 for i in range(min(len(faces), len(face_texture_ids))))
    textured_faces_count = 0
    if has_textured_faces:
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for i, poly in enumerate(mesh.polygons):
            if i < len(face_texture_ids) and face_texture_ids[i] != -1:
                coord_index = texture_coordinate_indices[i] if i < len(texture_coordinate_indices) else -1
               
                use_fallback = coord_index == -1 or not (0 <= coord_index < len(texture_triangles))
                if use_fallback:
                    p_idx, m_idx, n_idx = faces[i] # Use face vertices as PMN
                else:
                    p_idx, m_idx, n_idx = texture_triangles[coord_index]
                if all(0 <= idx < len(vertices) for idx in [p_idx, m_idx, n_idx]):
                    p, m, n = Vector(vertices[p_idx]), Vector(vertices[m_idx]), Vector(vertices[n_idx])
                    for loop_index in poly.loop_indices:
                        vert_idx = mesh.loops[loop_index].vertex_index
                        vert = Vector(vertices[vert_idx])
                        u, v = compute_uv_from_pmn(vert, p, m, n)
                        uv_layer.data[loop_index].uv = (u, 1.0 - v)
                    textured_faces_count += 1
        print(f"Applied UVs to {textured_faces_count} faces.")
    else:
        print("No textured faces, skipping UV map creation.")
           
    create_rs_data_layers(obj, mesh, face_priorities_data, face_tskins_data,
                          vertex_skins_data, has_priorities, has_tskins, has_vskins,
                          triangle_count, vertex_count)
    return {'FINISHED'}
def create_rs_data_layers(obj, mesh, face_priorities_data, face_tskins_data,
                          vertex_skins_data, has_priorities, has_tskins, has_vskins,
                          num_faces, num_vertices):
    """Create RuneScape-specific data layers"""
    if has_priorities and face_priorities_data:
        pri_layer = mesh.vertex_colors.new(name="RSPRI")
        for i, poly in enumerate(mesh.polygons):
            if i < len(face_priorities_data):
                color = (face_priorities_data[i] / 255.0, 0.0, 0.0, 1.0)
                for loop_index in poly.loop_indices:
                    pri_layer.data[loop_index].color = color
    if has_tskins and face_tskins_data:
        tskin_layer = mesh.vertex_colors.new(name="RSTSKIN")
        for i, poly in enumerate(mesh.polygons):
            if i < len(face_tskins_data):
                color = (face_tskins_data[i] / 255.0, 0.0, 0.0, 1.0)
                for loop_index in poly.loop_indices:
                    tskin_layer.data[loop_index].color = color
                   
    if has_vskins and vertex_skins_data:
        print(" > Creating VSKIN vertex groups...")
        max_weight = max(vertex_skins_data) if vertex_skins_data else 0
        max_total_weight = max_weight / 100.0
       
        vskin_groups = {}
        if max_total_weight > 0.0:
            vskin_groups[1] = obj.vertex_groups.new(name="VSKIN1:")
        if max_total_weight > 1.0:
            vskin_groups[2] = obj.vertex_groups.new(name="VSKIN2:")
        if max_total_weight > 2.0:
            vskin_groups[3] = obj.vertex_groups.new(name="VSKIN3:")
       
        for vertex_idx in range(min(num_vertices, len(vertex_skins_data))):
            skin_value = vertex_skins_data[vertex_idx]
            if skin_value > 0:
                total_weight = skin_value / 100.0
                w1 = min(1.0, total_weight)
                remaining = total_weight - w1
                w2 = min(1.0, remaining)
                w3 = remaining - w2
               
                if 1 in vskin_groups and w1 > 0.001:
                    vskin_groups[1].add([vertex_idx], w1, 'REPLACE')
                if 2 in vskin_groups and w2 > 0.001:
                    vskin_groups[2].add([vertex_idx], w2, 'REPLACE')
                if 3 in vskin_groups and w3 > 0.001:
                    vskin_groups[3].add([vertex_idx], w3, 'REPLACE')
# =============================================================================
# BLENDER OPERATOR (adjusted for 317)
# =============================================================================
class Import317Model(Operator, ImportHelper):
    """Import 317/OSRS Model (.dat)"""
    bl_idname = "import_scene.rs_317_model"
    bl_label = "Import 317/OSRS Model"
    bl_options = {'REGISTER', 'UNDO'}
   
    filename_ext = ".dat"
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})
    files: CollectionProperty(type=OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH')
   
    def execute(self, context):
        if self.files:
            for file_elem in self.files:
                filepath = os.path.join(self.directory, file_elem.name)
                with open(filepath, 'rb') as f:
                    data = f.read()
                import_old_format(data, filepath)
        else:
            with open(self.filepath, 'rb') as f:
                data = f.read()
            import_old_format(data, self.filepath)
        return {'FINISHED'}
def menu_func_import_317(self, context):
    self.layout.operator(Import317Model.bl_idname, text="317/OSRS Model (.dat)")
classes = (RS_Material_PropertyGroup, Import317Model,)
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Material.rs_pmn_mat = bpy.props.PointerProperty(type=RS_Material_PropertyGroup)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_317)
    print("Corrected RS Model Importer with Full Format Support registered")
def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_317)
    try:
        del bpy.types.Material.rs_pmn_mat
    except AttributeError:
        pass
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
if __name__ == "__main__":
    register()