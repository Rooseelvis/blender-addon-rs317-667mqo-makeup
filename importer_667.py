# importer_667.py - RuneScape 667 Model Importer
# Corrected to match robust material/UV handling from dat_importer.py

import bpy
import struct
import os
import math
import colorsys
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, CollectionProperty
from bpy.types import Operator, OperatorFileListElement
from mathutils import Vector, Matrix

# =============================================================================
# DATA STREAM
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
        val = self.read_byte()
        return val - 256 if val > 127 else val
    
    def read_unsigned_short(self):
        if self.offset + 1 >= len(self.data):
            return 0
        value = struct.unpack('>H', self.data[self.offset:self.offset+2])[0]
        self.offset += 2
        return value
    
    def read_signed_short(self):
        val = self.read_unsigned_short()
        return val - 65536 if val > 32767 else val
    
    def unpack_smart_int(self):
        byte1 = self.read_byte()
        if (byte1 & 0x80) == 0:
            return byte1 - 64
        else:
            byte2 = self.read_byte()
            value = (byte1 << 8) | byte2
            return value - 49152
    
    def remaining(self):
        return len(self.data) - self.offset

# =============================================================================
# COMPLEX TEXTURE PARAMETERS
# =============================================================================
class ComplexTextureParams:
    """Holds parameters for complex texture projections"""
    def __init__(self):
        self.scale_x = 128
        self.scale_y = 128
        self.scale_z = 128
        self.rotation = 0
        self.direction = 0
        self.speed = 0
        self.trans_u = 0
        self.trans_v = 0

# =============================================================================
# HELPER FUNCTIONS (Consistent with dat_importer.py)
# =============================================================================
def get_texture_dump_path():
    """Finds the texture_dump folder relative to the Blender AppData location"""
    appdata = os.getenv('APPDATA')
    if not appdata:
        return ""
    # Try to find the latest Blender version folder
    blender_root = os.path.join(appdata, "Blender Foundation", "Blender")
    if not os.path.exists(blender_root):
        return ""
    versions = sorted([d for d in os.listdir(blender_root) if os.path.isdir(os.path.join(blender_root, d))], reverse=True)
    blender_version = versions[0] if versions else "4.5"
    path = os.path.join(appdata, "Blender Foundation", "Blender", blender_version, "scripts", "addons", "polyforge_mqo_exporter", "texture_dump")
    return path

def find_texture_file(texture_id):
    """Finds the first matching texture file for a given ID"""
    texture_dirs = [get_texture_dump_path(), os.path.join(get_texture_dump_path(), "667Tex")]
    patterns = [str(texture_id), f"texture_{texture_id}", f"tex_{texture_id}", f"pmn_{texture_id}"]
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
                        return os.path.join(tex_dir, filename)
    return None

def setup_material_alpha(mat, alpha_byte):
    """Configures a material for alpha blending - CORRECTED from dat_importer.py"""
    if not mat or not mat.use_nodes:
        return
    
    # FIX: Invert the alpha value to match the game's format
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
    """Create a Blender material from HSL color value (Updated for spec)"""
    rgb = rune_hsl_to_rgb(hsl_value)
    mat = bpy.data.materials.new(name=f"RS_Color_{hsl_value}")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    output_node = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    bsdf_node = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf_node.name = "Principled BSDF"
    bsdf_node.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf_node.inputs['Roughness'].default_value = 1.0
    # Handle both versions of Specular socket
    if 'Specular' in bsdf_node.inputs:
        bsdf_node.inputs['Specular'].default_value = 0.0
    elif 'Specular IOR' in bsdf_node.inputs:
        bsdf_node.inputs['Specular IOR'].default_value = 1.0
    mat.node_tree.links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
    # Position nodes
    bsdf_node.location = (0, 0)
    output_node.location = (200, 0)
    return mat

def create_texture_material(texture_id):
    """Create a Blender material with full texture node setup (Updated with RSCOLOR)"""
    mat = bpy.data.materials.new(name=f"Texture_{texture_id}")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    
    output_node = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    bsdf_node = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf_node.name = "Principled BSDF"
    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex_coord_node = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    mapping_node = mat.node_tree.nodes.new('ShaderNodeMapping')
    mapping_node.name = 'RS Mapping'
    
    # Add overlay color support (RSCOLOR is used by the importer to pass the face color tint)
    attr_node = mat.node_tree.nodes.new('ShaderNodeAttribute')
    attr_node.attribute_name = "RSCOLOR"
    attr_node.attribute_type = 'GEOMETRY' # Must be GEOMETRY for VCol to Attribute Node
    mix_node = mat.node_tree.nodes.new('ShaderNodeMixRGB')
    mix_node.blend_type = 'MULTIPLY'
    mix_node.inputs['Fac'].default_value = 1.0 # Full multiply influence
    tex_node.extension = 'REPEAT'
    
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
    
    bsdf_node.inputs['Roughness'].default_value = 1.0
    if 'Specular' in bsdf_node.inputs:
        bsdf_node.inputs['Specular'].default_value = 0.0
    elif 'Specular IOR' in bsdf_node.inputs:
        bsdf_node.inputs['Specular IOR'].default_value = 1.0
    
    # Links with overlay
    mat.node_tree.links.new(tex_coord_node.outputs['UV'], mapping_node.inputs['Vector'])
    mat.node_tree.links.new(mapping_node.outputs['Vector'], tex_node.inputs['Vector'])
    mat.node_tree.links.new(tex_node.outputs['Color'], mix_node.inputs['Color1'])
    mat.node_tree.links.new(attr_node.outputs['Color'], mix_node.inputs['Color2'])
    mat.node_tree.links.new(mix_node.outputs['Color'], bsdf_node.inputs['Base Color'])
    mat.node_tree.links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
    
    # Position nodes
    tex_coord_node.location = (-600, 100)
    mapping_node.location = (-400, 100)
    tex_node.location = (-200, 100)
    attr_node.location = (-200, -100)
    mix_node.location = (0, 0)
    bsdf_node.location = (200, 0)
    output_node.location = (400, 0)
    
    return mat

# =============================================================================
# UV COMPUTATION FUNCTIONS (from dat_importer.py)
# =============================================================================
def compute_uv_from_pmn(vert, p, m, n):
    """Computes UV coordinates for a vertex based on PMN basis (Simple Texture)"""
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

# DISABLED - Complex textures not working correctly yet (Preserved as placeholders)
def compute_uv_cylindrical(vert, params):
    """Placeholder - returns 0,0 until fixed"""
    return 0.0, 0.0

def compute_uv_cube(vert, normal, params):
    """Placeholder - returns 0,0 until fixed"""
    return 0.0, 0.0

def compute_uv_spherical(vert, params):
    """Placeholder - returns 0,0 until fixed"""
    return 0.0, 0.0

# =============================================================================
# 667 FORMAT DECODER (Updated to use correct utility functions)
# =============================================================================
def decode_667_format(data, filepath):
    """Decode 667 versioned format with complex texture support"""
    print("=== DECODING 667 VERSIONED FORMAT WITH COMPLEX TEXTURES ===")
    if len(data) < 23:
        return {'CANCELLED'}
    
    footer_start = len(data) - 23
    footer_data = data[footer_start:footer_start + 21]
    vertex_count = struct.unpack('>H', footer_data[0:2])[0]
    triangle_count = struct.unpack('>H', footer_data[2:4])[0]
    textured_triangle_count = footer_data[4]
    footer_flags = footer_data[5]
    triangle_priority_flag = footer_data[6]
    triangle_alpha_flag = footer_data[7]
    triangle_skin_flag = footer_data[8]
    texture_flag = footer_data[9]
    vertex_skin_flag = footer_data[10]
    vertices_x_length = struct.unpack('>H', footer_data[11:13])[0]
    vertices_y_length = struct.unpack('>H', footer_data[13:15])[0]
    vertices_z_length = struct.unpack('>H', footer_data[15:17])[0]
    triangle_indices_length = struct.unpack('>H', footer_data[17:19])[0]
    texture_coord_indices_length = struct.unpack('>H', footer_data[19:21])[0]
    
    print(f"Vertices: {vertex_count}, Triangles: {triangle_count}, Textured: {textured_triangle_count}")
    
    # Read texture render types
    render_type_stream = DataStream(data)
    texture_render_types = [render_type_stream.read_byte() for _ in range(textured_triangle_count)]
    
    simple_texture_face_count = texture_render_types.count(0)
    complex_texture_face_count = sum(1 for t in texture_render_types if t in [1, 2, 3])
    cube_texture_face_count = texture_render_types.count(2)
    
    print(f"Texture types - Simple: {simple_texture_face_count}, Complex: {complex_texture_face_count}, Cube: {cube_texture_face_count}")
    
    # Calculate offsets
    pos = textured_triangle_count
    vertex_flags_offset = pos; pos += vertex_count
    triangle_info_offset = pos
    if footer_flags & 1 == 1: pos += triangle_count
    triangle_indices_flags_offset = pos; pos += triangle_count
    triangle_priorities_offset = pos
    if triangle_priority_flag == 255: pos += triangle_count
    triangle_skin_offset = pos
    if triangle_skin_flag == 1: pos += triangle_count
    vertex_skin_offset = pos
    if vertex_skin_flag == 1: pos += vertex_count
    triangle_alpha_offset = pos
    if triangle_alpha_flag == 1: pos += triangle_count
    triangle_indices_offset = pos; pos += triangle_indices_length
    triangle_materials_offset = pos
    if texture_flag == 1: pos += triangle_count * 2
    texture_coordinate_indices_offset = pos; pos += texture_coord_indices_length
    triangle_colors_offset = pos; pos += triangle_count * 2
    vertices_x_offset = pos; pos += vertices_x_length
    vertices_y_offset = pos; pos += vertices_y_length
    vertices_z_offset = pos; pos += vertices_z_length
    simple_textures_offset = pos; pos += simple_texture_face_count * 6
    complex_textures_offset = pos; pos += complex_texture_face_count * 6
    
    # === START OF INEFFICIENT/COMPLEX TEXTURE READING BLOCK ===
    # Reading complex texture parameters - matching exact game order
    texture_bytes = 6 # Simplified default size
    textures_scale_offset = pos; pos += complex_texture_face_count * texture_bytes # Reads Z, Speed, X
    textures_rotation_offset = pos; pos += complex_texture_face_count
    textures_direction_offset = pos; pos += complex_texture_face_count
    textures_translation_offset = pos
    
    scale_stream = DataStream(data[textures_scale_offset:])
    rot_stream = DataStream(data[textures_rotation_offset:])
    dir_stream = DataStream(data[textures_direction_offset:])
    trans_stream = DataStream(data[textures_translation_offset:])
    
    # Track which complex textures are cubes (need extra trans params)
    cube_indices_in_complex_list = []
    complex_counter = 0
    for r_type in texture_render_types:
        if r_type in [1, 2, 3]:
            if r_type == 2:
                cube_indices_in_complex_list.append(complex_counter)
            complex_counter += 1
    
    complex_params = []
    for i in range(complex_texture_face_count):
        p = ComplexTextureParams()
        # Scale buffer contains 3 values in order: Z, Speed, X
        p.scale_z = scale_stream.read_unsigned_short()
        p.speed = scale_stream.read_unsigned_short()
        p.scale_x = scale_stream.read_unsigned_short()
        # Single byte values
        p.rotation = rot_stream.read_signed_byte()
        p.scale_y = dir_stream.read_signed_byte()  # Actually used as direction/scale
        p.direction = trans_stream.read_signed_byte()  # Base direction value
        complex_params.append(p)
    
    # Cube textures read 2 additional translation bytes
    for cube_idx in cube_indices_in_complex_list:
        if cube_idx < len(complex_params):
            complex_params[cube_idx].trans_u = trans_stream.read_signed_byte()
            complex_params[cube_idx].trans_v = trans_stream.read_signed_byte()
    # === END OF INEFFICIENT/COMPLEX TEXTURE READING BLOCK ===

    # Read vertices
    vertices = []
    vertex_flags_data = data[vertex_flags_offset:vertex_flags_offset + vertex_count]
    x_stream = DataStream(data[vertices_x_offset:vertices_x_offset + vertices_x_length])
    y_stream = DataStream(data[vertices_y_offset:vertices_y_offset + vertices_y_length])
    z_stream = DataStream(data[vertices_z_offset:vertices_z_offset + vertices_z_length])
    start_x = start_y = start_z = 0
    for vertex in range(vertex_count):
        position_flag = vertex_flags_data[vertex] if vertex < len(vertex_flags_data) else 0
        x_off = x_stream.unpack_smart_int() if (position_flag & 1) != 0 else 0
        y_off = y_stream.unpack_smart_int() if (position_flag & 2) != 0 else 0
        z_off = z_stream.unpack_smart_int() if (position_flag & 4) != 0 else 0
        start_x += x_off
        start_y += y_off
        start_z += z_off
        vertices.append((start_x, start_z, -start_y))

    # Read faces
    faces = []
    indices_data = data[triangle_indices_offset:triangle_indices_offset + triangle_indices_length]
    flags_data = data[triangle_indices_flags_offset:triangle_indices_flags_offset + triangle_count]
    indices_stream = DataStream(indices_data)
    a = b = c = 0
    last = 0
    for triangle_index in range(triangle_count):
        opcode = flags_data[triangle_index] if triangle_index < len(flags_data) else 1
        if opcode == 1:
            a = indices_stream.unpack_smart_int() + last; last = a
            b = indices_stream.unpack_smart_int() + last; last = b
            c = indices_stream.unpack_smart_int() + last; last = c
        elif opcode == 2:
            b = c; c = indices_stream.unpack_smart_int() + last; last = c
        elif opcode == 3:
            a = c; c = indices_stream.unpack_smart_int() + last; last = c
        elif opcode == 4:
            tmp = a; a = b; b = tmp
            c = indices_stream.unpack_smart_int() + last; last = c
        a = max(0, min(a, vertex_count - 1))
        b = max(0, min(b, vertex_count - 1))
        c = max(0, min(c, vertex_count - 1))
        faces.append((a, b, c))

    # Read face colors
    face_colors_data = data[triangle_colors_offset:triangle_colors_offset + triangle_count * 2]
    face_colors = list(struct.unpack(f'>{triangle_count}H', face_colors_data[:triangle_count * 2]))

    # Read texture IDs
    face_texture_ids = [-1] * triangle_count
    if texture_flag == 1:
        material_data = data[triangle_materials_offset:triangle_materials_offset + triangle_count * 2]
        for i in range(triangle_count):
            if i * 2 + 2 <= len(material_data):
                tex_id = struct.unpack('>H', material_data[i*2:(i+1)*2])[0] - 1
                face_texture_ids[i] = tex_id

    # Read texture coordinate indices
    texture_coordinate_indices = [-1] * triangle_count
    if texture_coord_indices_length > 0:
        coord_data = data[texture_coordinate_indices_offset:texture_coordinate_indices_offset + texture_coord_indices_length]
        coord_stream = DataStream(coord_data)
        for i in range(triangle_count):
            if face_texture_ids[i] != -1 and coord_stream.remaining() > 0:
                coord_index = coord_stream.read_byte() - 1
                texture_coordinate_indices[i] = coord_index

    # Read texture triangles
    texture_triangles = []
    simple_stream = DataStream(data[simple_textures_offset:])
    complex_stream = DataStream(data[complex_textures_offset:])
    for i in range(textured_triangle_count):
        render_type = texture_render_types[i]
        if render_type == 0 and simple_stream.remaining() >= 6:
            p = simple_stream.read_signed_short()
            m = simple_stream.read_signed_short()
            n = simple_stream.read_signed_short()
            texture_triangles.append((p, m, n))
        elif render_type in [1, 2, 3] and complex_stream.remaining() >= 6:
            p = complex_stream.read_signed_short()
            m = complex_stream.read_signed_short()
            n = complex_stream.read_signed_short()
            texture_triangles.append((p, m, n))
        else:
            texture_triangles.append((0, 0, 0))

    # Read additional data
    face_priorities_data = data[triangle_priorities_offset:triangle_priorities_offset + triangle_count] if triangle_priority_flag == 255 else b''
    face_tskins_data = data[triangle_skin_offset:triangle_skin_offset + triangle_count] if triangle_skin_flag == 1 else b''
    vertex_skins_data = data[vertex_skin_offset:vertex_skin_offset + vertex_count] if vertex_skin_flag == 1 else b''
    face_alphas_data = data[triangle_alpha_offset:triangle_alpha_offset + triangle_count] if triangle_alpha_flag == 1 else b''
    
    return create_667_mesh(vertices, faces, face_colors, face_texture_ids,
                           texture_coordinate_indices, texture_triangles, texture_render_types, complex_params, filepath,
                           face_priorities_data, face_tskins_data, vertex_skins_data, face_alphas_data,
                           triangle_priority_flag == 255, triangle_skin_flag == 1, 
                           vertex_skin_flag == 1, triangle_count, vertex_count)

def create_667_mesh(vertices, faces, face_colors, face_texture_ids,
                    texture_coordinate_indices, texture_triangles, texture_render_types, complex_params, filepath,
                    face_priorities_data, face_tskins_data, vertex_skins_data, face_alphas_data,
                    has_priorities, has_tskins, has_vskins, triangle_count, vertex_count):
    """Create mesh for 667 format with complex texture support - CORRECTED material/UV flow"""
    model_name = os.path.splitext(os.path.basename(filepath))[0]
    mesh = bpy.data.meshes.new(name=f"{model_name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    
    obj = bpy.data.objects.new(name=model_name, object_data=mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    if face_alphas_data:
        face_alphas = list(face_alphas_data)
    else:
        face_alphas = [255] * triangle_count
    
    # Create materials 
    material_map = {}
    face_material_indices = [0] * len(faces)
    
    for i in range(min(triangle_count, len(faces))):
        alpha_val = face_alphas[i] if i < len(face_alphas) else 255
        
        if i < len(face_texture_ids) and face_texture_ids[i] != -1:
            tex_id = face_texture_ids[i]
            coord_index = texture_coordinate_indices[i] if i < len(texture_coordinate_indices) else -1
            mat_key = ('tex', tex_id, coord_index, alpha_val)
            
            if mat_key not in material_map:
                mat = create_texture_material(tex_id)
                if alpha_val < 255 and len(face_alphas_data) > 0:
                    mat.name = f"Texture_{tex_id}_Alpha_{alpha_val}"
                    setup_material_alpha(mat, alpha_val)
                material_map[mat_key] = len(obj.data.materials)
                obj.data.materials.append(mat)
            face_material_indices[i] = material_map[mat_key]
        else:
            hsl = face_colors[i] if i < len(face_colors) else 0
            mat_key = ('color', hsl, alpha_val)
            if mat_key not in material_map:
                mat = create_material_from_hsl(hsl)
                if alpha_val < 255 and len(face_alphas_data) > 0:
                    mat.name = f"RS_Color_{hsl}_Alpha_{alpha_val}"
                    setup_material_alpha(mat, alpha_val)
                material_map[mat_key] = len(obj.data.materials)
                obj.data.materials.append(mat)
            face_material_indices[i] = material_map[mat_key]
    
    if mesh.polygons:
        for i, poly in enumerate(mesh.polygons):
            if i < len(face_material_indices):
                poly.material_index = face_material_indices[i]
    
    # Create overlay color vertex layer for 667
    print(" > Creating RSCOLOR vertex color layer for overlay...")
    color_layer = mesh.vertex_colors.new(name="RSCOLOR")
    for i, poly in enumerate(mesh.polygons):
        if i < len(face_texture_ids) and face_texture_ids[i] != -1:
            # Textured face: use the face HSL color as the tint (stored in face_colors[i])
            hsl = face_colors[i] if i < len(face_colors) else 0
            rgb = rune_hsl_to_rgb(hsl)
            col = (*rgb, 1.0)
        else:
            # Non-textured face: no tint (white)
            col = (1.0, 1.0, 1.0, 1.0)
        for loop_index in poly.loop_indices:
            color_layer.data[loop_index].color = col
    
    # Create UV map with complex texture support
    print(" > Creating UV map with complex texture projection support...")
    uv_layer = mesh.uv_layers.new(name="UVMap")
    textured_faces_count = 0
    complex_tex_params_used = 0
    
    for i, poly in enumerate(mesh.polygons):
        if i >= min(triangle_count, len(faces)):
            continue
        
        # This block correctly assigns UVs using the appropriate method.
        if i < len(face_texture_ids) and face_texture_ids[i] != -1:
            coord_index = texture_coordinate_indices[i] if i < len(texture_coordinate_indices) else -1
            
            if coord_index == -1 or coord_index >= len(texture_triangles):
                # No UV coordinates provided - fallback to no UV
                for loop_index in poly.loop_indices:
                    uv_layer.data[loop_index].uv = (0.0, 0.0)
                continue
            
            render_type = texture_render_types[coord_index] if coord_index < len(texture_render_types) else 0
            
            # Get texture parameters for complex types
            params = None
            if render_type in [1, 2, 3]:
                if complex_tex_params_used < len(complex_params):
                    params = complex_params[complex_tex_params_used]
            
            # Get PMN vertices (from texture_triangles for this coord_index)
            p_idx, m_idx, n_idx = texture_triangles[coord_index]
            if not all(0 <= idx < len(vertices) for idx in [p_idx, m_idx, n_idx]):
                # Invalid PMN indices - fallback to no UV
                for loop_index in poly.loop_indices:
                    uv_layer.data[loop_index].uv = (0.0, 0.0)
                continue
            
            p = Vector(vertices[p_idx])
            m = Vector(vertices[m_idx])
            n = Vector(vertices[n_idx])
            
            # Compute UVs for each vertex in the face
            for loop_index in poly.loop_indices:
                vert_idx = mesh.loops[loop_index].vertex_index
                if 0 <= vert_idx < len(vertices):
                    vert = Vector(vertices[vert_idx])
                    normal = poly.normal
                    u, v = 0.0, 0.0
                    
                    # Compute UV based on render type
                    if render_type == 0:  # Simple texture (PMN)
                        u, v = compute_uv_from_pmn(vert, p, m, n)
                    elif params:
                        # COMPLEX TYPE: This relies on the placeholder functions above
                        if render_type == 1:  # Cylindrical
                            u, v = compute_uv_cylindrical(vert, params.__dict__)
                        elif render_type == 2:  # Cube
                            u, v = compute_uv_cube(vert, normal, params.__dict__)
                        elif render_type == 3:  # Spherical
                            u, v = compute_uv_spherical(vert, params.__dict__)
                    
                    uv_layer.data[loop_index].uv = (u, 1.0 - v)
            
            textured_faces_count += 1
            
            # Increment complex params counter if we used one
            if render_type in [1, 2, 3]:
                complex_tex_params_used += 1
        else:
             # Non-textured face - no UV (0.0, 0.0) is the safe default
            for loop_index in poly.loop_indices:
                uv_layer.data[loop_index].uv = (0.0, 0.0)
    
    print(f"Applied UVs to {textured_faces_count} textured faces")
    
    # Create RS data layers
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
        max_weight = max(vertex_skins_data) if vertex_skins_data else 0
        max_total_weight = max_weight / 100.0
        
        vskin_groups = {}
        if max_total_weight > 0.0:
            vskin_groups[1] = obj.vertex_groups.new(name="VSKIN1:")
        if max_total_weight > 1.0:
            vskin_groups[2] = obj.vertex_groups.new(name="VSKIN2:")
        if max_total_weight > 2.0:
            vskin_groups[3] = obj.vertex_groups.new(name="VSKIN3:")
        
        for vertex_idx in range(min(vertex_count, len(vertex_skins_data))):
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
    
    print(f"--- Successfully imported 667 model {model_name}.dat ---")
    return {'FINISHED'}

# =============================================================================
# BLENDER OPERATOR
# =============================================================================
class Import667Model(Operator, ImportHelper):
    """Import 667 Model (.dat)"""
    bl_idname = "import_scene.rs_667_model"
    bl_label = "Import 667 Model"
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
                decode_667_format(data, filepath)
        else:
            with open(self.filepath, 'rb') as f:
                data = f.read()
            decode_667_format(data, self.filepath)
        return {'FINISHED'}

def menu_func_import_667(self, context):
    self.layout.operator(Import667Model.bl_idname, text="667 Model (.dat)")

classes = (Import667Model,)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_667)
    print("667 Model Importer (Enhanced with Complex Textures) registered")

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_667)
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

if __name__ == "__main__":
    register()