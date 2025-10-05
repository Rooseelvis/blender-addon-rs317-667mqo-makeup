import bpy
import struct
import re
from mathutils import Vector, Matrix
from math import inf
import colorsys

# This can be left empty if you are defining colors directly in Blender materials.
MATERIALS = []

DROP_PRESETS = ['HEAD', 'BODY', 'GLOVES', 'PANTS', 'BOOTS', 'SWORD', 'SHIELD', 'NECKLACE', 'CAPE']

DROP_PARAMS = {
    'HEAD': {
        'rot_value': 0,
        'rot_x_value': -1.5708,
        'trans_z': -168.785,
        'trans_type': 'GLOBAL'
    },
    'BODY': {
        'rot_value': 0,
        'rot_x_value': -1.5708,
        'trans_z': -130.459,
        'trans_type': 'GLOBAL'
    },
    'GLOVES': {
        'rot_value': 0,
        'rot_x_value': -1.5708,
        'trans_z': -92.5906,
        'trans_type': 'GLOBAL'
    },
    'PANTS': {
        'rot_value': 0,
        'rot_x_value': -1.5708,
        'trans_z': -57.3615,
        'trans_type': 'GLOBAL'
    },
    'BOOTS': {
        # No rotation or translation
    },
    'SWORD': {
        'rot_value': 1.5708,
        'rot_orient_matrix': ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
        'trans_value': (32.2849, 0, -84.0625),
        'trans_type': 'GLOBAL'
    },
    'SHIELD': {
        'rot_value': -1.5708,
        'rot_orient_matrix': ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
        'trans_value': (-39.2901, 0, -84.9762),
        'trans_type': 'GLOBAL'
    },
    'NECKLACE': {
        'rot_value': 1.5708,
        'rot_orient_matrix': ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
        'trans_value': (0, 15.3505, -140.348),
        'trans_type': 'GLOBAL'
    },
    'CAPE': {
        'rot_value': 0,
        'rot_x_value': 1.4908,
        'trans_z': -89.3615,
        'trans_type': 'GLOBAL'
    }
}

def rgb_to_rune_hsl(r_float, g_float, b_float):
    """Converts a 0.0-1.0 float RGB color to a 16-bit RuneScape HSL integer with correct rounding."""
    h, s, v = colorsys.rgb_to_hsv(r_float, g_float, b_float)
    
    h_val = round(h * 63)
    s_val = round(s * 7)
    l_val = round(v * 127)
    
    return (h_val << 10) | (s_val << 7) | l_val

def pack_smart_int(value):
    """Packs an integer using variable-length encoding."""
    if -64 <= value <= 63:
        return struct.pack('>B', value + 64)
    else:
        return struct.pack('>H', value + 49152)

def pack_word(value):
    """Packs an integer as a 2-byte big-endian unsigned short."""
    return struct.pack('>H', value)

def extract_texture_id_from_material_name(mat_name):
    """Extract texture ID from material name, handling various naming patterns."""
    patterns = [
        r'PMN_(\d+)\.png', r'PMN_(\d+)\.jpg', r'PMN_(\d+)\.jpeg', 
        r'PMN_(\d+)\.tga', r'PMN_(\d+)\.bmp', r'PMN_(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, mat_name)
        if match:
            return int(match.group(1))
    match = re.search(r'PMN_.*?(\d+)', mat_name)
    if match:
        return int(match.group(1))
    print(f"Warning: Could not extract texture ID from material name '{mat_name}'. Using 0.")
    return 0

def detect_model_type(obj):
    """Detects the model type based on VSKIN vertex groups."""
    if not obj or obj.type != 'MESH':
        return 'UNKNOWN'
    
    vskin_groups = [vg for vg in obj.vertex_groups if re.match(r'^VSKIN\d+:$', vg.name)]
    if not vskin_groups:
        return 'UNKNOWN'
    
    # Get all VSKIN weights present in the model
    vskin_weights = set()
    mesh = obj.data
    for vg in vskin_groups:
        for v in mesh.vertices:
            for g in v.groups:
                if g.group == vg.index and g.weight > 0:
                    vskin_weights.add(int(g.weight * 100))
    
    # Define detection patterns based on unique VSKIN weights
    detection_patterns = {
        'HEAD': {1, 2, 3},
        'BODY': {8, 25, 21, 26, 20, 23, 17, 22, 19},
        'GLOVES': {28, 27},
        'PANTS': {29, 41, 40, 42, 43, 44, 35, 34, 36, 33, 37, 31, 38, 32},
        'BOOTS': {38, 32, 47, 48, 46, 45},
        'SWORD': {50},
        'SHIELD': {28},
        'NECKLACE': {8},
        'CAPE': {8, 10, 11, 9, 14, 15, 13, 12}  # Add cape detection pattern
    }
    
    # Check for best match
    best_match = 'UNKNOWN'
    best_match_count = 0
    
    for model_type, pattern in detection_patterns.items():
        match_count = len(vskin_weights & pattern)
        if match_count > best_match_count:
            best_match_count = match_count
            best_match = model_type
    
    # Special handling for overlapping patterns
    if best_match_count > 0:
        # SHIELD and GLOVES both use weight 28, check for 27 to distinguish
        if 28 in vskin_weights and 27 in vskin_weights:
            return 'GLOVES'
        elif 28 in vskin_weights and 27 not in vskin_weights and best_match in ['SHIELD', 'GLOVES']:
            return 'SHIELD'
        
        # BODY and NECKLACE both use weight 8
        if 8 in vskin_weights and len(vskin_weights & detection_patterns['BODY']) > 1:
            return 'BODY'
        elif 8 in vskin_weights and len(vskin_weights) == 1:
            return 'NECKLACE'
        
        return best_match
    
    return 'UNKNOWN'

def _export_core(filepath, obj, export_preset, drop_mode):
    if not obj or obj.type != 'MESH':
        print(f"Object '{obj.name}' is not a mesh. Skipping.")
        return
    mode_str = " (Drop Mode)" if drop_mode else ""
    print(f"\n--- Starting DAT Export for '{obj.name}' (Preset: {export_preset}{mode_str}) ---")
    
    # --- 1. DATA GATHERING & PREPARATION ---
    print("[1] GATHERING & PREPARING DATA:")
    
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    mesh.calc_loop_triangles()
    
    uv_layer = mesh.uv_layers.active
    has_uvs = uv_layer is not None
    
    world_matrix = obj.matrix_world
    
    # Compute original world vertices for median if needed
    original_vertices_raw = [world_matrix @ v.co for v in mesh.vertices]
    num_vertices = len(original_vertices_raw)
    faces_raw = list(mesh.loop_triangles)
    num_faces = len(faces_raw)
    print(f" > Found {num_vertices} vertices and {num_faces} faces.")
    
    # Default final matrix
    final_matrix = world_matrix
    
    # Compute final world matrix and vertices_raw
    if drop_mode and export_preset in DROP_PARAMS:
        params = DROP_PARAMS[export_preset]
        median = sum(original_vertices_raw, Vector()) / num_vertices
        T = Matrix.Translation(median)
        
        rot_value = params.get('rot_value', 0)
        if rot_value != 0:
            orient_matrix_list = params['rot_orient_matrix']
            orient_mat = Matrix(orient_matrix_list)
            axis = (orient_mat @ Vector((0, 0, 1))).normalized()
            delta_rot = Matrix.Rotation(rot_value, 4, axis)
            delta_trans_rot = T @ delta_rot @ T.inverted()
            after_rot_matrix = delta_trans_rot @ world_matrix
        else:
            after_rot_matrix = world_matrix
        
        rot_x_value = params.get('rot_x_value', 0)
        if rot_x_value != 0:
            delta_rot_x = Matrix.Rotation(rot_x_value, 4, Vector((1, 0, 0)))
            delta_trans_rot_x = T @ delta_rot_x @ T.inverted()
            after_rot_matrix = delta_trans_rot_x @ after_rot_matrix
        
        trans_type = params.get('trans_type')
        if trans_type:
            if trans_type == 'LOCAL':
                trans_z = params['trans_z']
                local_vec = Vector((0, 0, trans_z))
                trans_mat = Matrix.Translation(local_vec)
                final_matrix = after_rot_matrix @ trans_mat
            else:  # GLOBAL
                if 'trans_value' in params:
                    trans_vec = Vector(params['trans_value'])
                elif 'trans_z' in params:
                    trans_vec = Vector((0, 0, params['trans_z']))
                else:
                    trans_vec = Vector((0, 0, 0))
                final_matrix = Matrix.Translation(trans_vec) @ after_rot_matrix
        else:
            final_matrix = after_rot_matrix
    
    vertices_raw = [final_matrix @ v.co for v in mesh.vertices]
    
    # ============================ VSKIN LOGIC ============================
    vskin_groups = [vg for vg in obj.vertex_groups if re.match(r'^VSKIN\d+:$', vg.name)]
    
    vertex_skins = [0] * num_vertices
    
    if vskin_groups:
        print(f" > Found {len(vskin_groups)} VSKIN groups. Summing weights...")
        vskin_group_indices = {vg.index for vg in vskin_groups}

        for i, vert in enumerate(mesh.vertices):
            summed_weight = 0.0
            for g in vert.groups:
                if g.group in vskin_group_indices:
                    summed_weight += g.weight * 100.0
            
            final_skin_value = min(254, int(round(summed_weight)))
            vertex_skins[i] = final_skin_value
        
        print(f" > Calculated summed vertex skin weights.")
    else:
        print(" > No VSKIN groups found. Skipping VSKIN data.")
    
    has_vertex_skins = not drop_mode and bool(vskin_groups)
    
    # ============================ TEXTURE LOGIC ============================
    face_colors_hsl = []
    face_textures = []
    texture_triangles = []
    pmn_material_map = {}
    texture_id_map = {}
    print(" > Processing materials for face colors and textures...")
    
    pmn_materials = []
    if obj.data.materials:
        for mat in obj.data.materials:
            if mat and mat.name.startswith('PMN_'):
                pmn_materials.append(mat)
    
    for mat in pmn_materials:
        extracted_id = extract_texture_id_from_material_name(mat.name)
        texture_id_map[mat.name] = extracted_id
        
    for tri_index, tri in enumerate(faces_raw):
        mat = obj.data.materials[tri.material_index] if obj.data.materials and tri.material_index < len(obj.data.materials) else None
        is_textured = False
        texture_id = 0
        
        if mat and mat.name.startswith("PMN_"):
            is_textured = True
            texture_id = texture_id_map.get(mat.name, 0)
            
            if mat.name not in pmn_material_map:
                p_idx, m_idx, n_idx = None, None, None
                if has_uvs:
                    A, B, C = mesh.vertices[tri.vertices[0]].co, mesh.vertices[tri.vertices[1]].co, mesh.vertices[tri.vertices[2]].co
                    loops = [mesh.loops[i] for i in tri.loops]
                    Ua, Va = uv_layer.data[loops[0].index].uv.x, 1.0 - uv_layer.data[loops[0].index].uv.y
                    Ub, Vb = uv_layer.data[loops[1].index].uv.x, 1.0 - uv_layer.data[loops[1].index].uv.y
                    Uc, Vc = uv_layer.data[loops[2].index].uv.x, 1.0 - uv_layer.data[loops[2].index].uv.y
                    det = (Ub - Ua) * (Vc - Va) - (Uc - Ua) * (Vb - Va)
                    
                    if abs(det) > 1e-6:
                        sP, tP = (((Vc - Va) * (0 - Ua) - (Uc - Ua) * (0 - Va)) / det, ((Ub - Ua) * (0 - Va) - (Vb - Va) * (0 - Ua)) / det)
                        P = A + sP * (B - A) + tP * (C - A)
                        sM, tM = (((Vc - Va) * (1 - Ua) - (Uc - Ua) * (0 - Va)) / det, ((Ub - Ua) * (0 - Va) - (Vb - Va) * (1 - Ua)) / det)
                        M = A + sM * (B - A) + tM * (C - A)
                        sN, tN = (((Vc - Va) * (0 - Ua) - (Uc - Ua) * (1 - Va)) / det, ((Ub - Ua) * (1 - Va) - (Vb - Va) * (0 - Ua)) / det)
                        N = A + sN * (B - A) + tN * (C - A)
                        
                        indices = []
                        for pos in [P, M, N]:
                            best_i, min_dist_sq = -1, inf
                            for i, v in enumerate(mesh.vertices):
                                dist_sq = (v.co - pos).length_squared
                                if dist_sq < min_dist_sq:
                                    min_dist_sq, best_i = dist_sq, i
                            indices.append(best_i)
                        p_idx, m_idx, n_idx = indices
                
                if p_idx is not None and m_idx is not None and n_idx is not None:
                    pmn_material_map[mat.name] = len(texture_triangles)
                    texture_triangles.append((p_idx, m_idx, n_idx))
                else:
                    is_textured = False
            
            if is_textured:
                pmn_index = pmn_material_map[mat.name]
                face_textures.append(2 + (pmn_index << 2))
                
        if not is_textured:
            face_textures.append(0)
            color_val = 0
            if mat and mat.use_nodes:
                principled = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                if principled:
                    color = principled.inputs["Base Color"].default_value
                    color_val = rgb_to_rune_hsl(color[0], color[1], color[2])
            face_colors_hsl.append(color_val)
        else:
            face_colors_hsl.append(texture_id)
            
    has_textures = bool(texture_triangles)
    num_tex_triangles = len(texture_triangles)
    print(f" > Found {num_tex_triangles} unique PMN texture definitions.")
    
    # ============================ PRIORITY LOGIC ============================
    has_priorities = True
    print(f" > Using '{export_preset}' export preset for priorities.")
    
    preset_maps = {
        'HEAD': ({1, 2, 3}, 6),
        'BODY': ({8}, 3, {25, 21, 26, 20, 23, 17, 22, 19}, 10),
        'GLOVES': ({28, 27}, 10),
        'PANTS': ({29, 41, 40, 42, 43, 44, 35, 34, 36, 33, 37, 31, 38, 32}, 1),
        'BOOTS': ({38, 32, 47, 48, 46, 45}, 0),
        'SWORD': ({50}, 10),
        'SHIELD': ({28}, 11),
        'NECKLACE': ({8}, 4)
    }
    
    face_first_vertices = []
    v1, v2, v3 = 0, 0, 0
    for tri in faces_raw:
        p1, p2, p3 = tri.vertices
        if (v1, v2) == (p2, p1):
            face_first_vertices.append(v2)
            v1, v2, v3 = v2, v1, p3
        elif p1 == v3 and p2 == v2:
            face_first_vertices.append(v3)
            v1, v2, v3 = v3, v2, p3
        elif p1 == v1 and p2 == v3:
            face_first_vertices.append(v1)
            v1, v2, v3 = v1, v3, p3
        else:
            face_first_vertices.append(p1)
            v1, v2, v3 = p1, p2, p3
    
    face_priorities = [1] * num_faces

    if export_preset == 'CUSTOM_PRIORITY':
        print(" > Using CUSTOM_PRIORITY preset. Reading from 'RSPRI' vertex color layer...")
        vcol_layer = mesh.vertex_colors.get("RSPRI")
        if vcol_layer:
            for i, tri in enumerate(faces_raw):
                color = vcol_layer.data[tri.loops[0]].color
                face_priorities[i] = int(color[0] * 255)
            print(f" > Successfully read custom priorities for {num_faces} faces.")
        else:
            print(" > WARNING: 'CUSTOM_PRIORITY' preset but 'RSPRI' layer not found! Using default priority 1.")
            
    elif export_preset in preset_maps:
        mappings = preset_maps[export_preset]
        if export_preset == 'BODY':
            weights_p3, pri_p3, weights_p10, pri_p10 = mappings
            for i in range(num_faces):
                v_index = face_first_vertices[i]
                weight_val = vertex_skins[v_index] if v_index < len(vertex_skins) else 0
                if weight_val in weights_p3: face_priorities[i] = pri_p3
                elif weight_val in weights_p10: face_priorities[i] = pri_p10
        else:
            weights, priority = mappings
            for i in range(num_faces):
                v_index = face_first_vertices[i]
                weight_val = vertex_skins[v_index] if v_index < len(vertex_skins) else 0
                if weight_val in weights: face_priorities[i] = priority
    
    # ============================ TSKIN LOGIC ============================
    face_tskins = [0] * num_faces
    
    tskin_preset_maps = {
        'HEAD': {
            1: 0,
            2: 1, 3: 1
        },
        'GLOVES': {
            27: 15,
            28: 16
        },
        'BODY': {
            8: 4,
            25: 13, 26: 13,
            23: 14,
            22: 12,
            21: 11, 20: 11,
            17: 8,
            19: 10
        },
        'PANTS': {
            29: 22, 41: 22,
            43: 23,
            35: 20, 36: 20, 37: 20,
            38: 21,
            44: 24,
            34: 19, 33: 19, 31: 19,
            32: 18
        },
        'BOOTS': {
            38: 21, 47: 21,
            46: 26,
            32: 18, 48: 18,
            45: 25
        },
        'SWORD': {
            50: 29
        },
        'SHIELD': {
            28: 16
        },
        'NECKLACE': {
            8: 4
        }
    }
    
    ordered_priority_maps = {
        'BOOTS': [
            {46, 45}
        ],
        'BODY': [
            {23},
            {25, 26},
            {17},
            {21, 20},
            {22},
            {19}
        ],
        'PANTS': [
            {44},
            {43},
            {38},
            {32},
            {35, 36, 37},
            {34, 33, 31},
        ]
    }
    
    if export_preset == 'CUSTOM_PRIORITY':
        tskin_vcol_layer = mesh.vertex_colors.get("RSTSKIN")
        if tskin_vcol_layer:
            print(" > Found 'RSTSKIN' vertex color layer. Reading TSKIN data...")
            for i, tri in enumerate(faces_raw):
                loop_index = tri.loops[0]
                color = tskin_vcol_layer.data[loop_index].color
                face_tskins[i] = int(color[0] * 255)
            print(f" > Successfully read TSKIN data for {num_faces} faces.")
        else:
            print(" > No 'RSTSKIN' layer found for CUSTOM_PRIORITY. Skipping TSKIN data.")
    
    elif export_preset in tskin_preset_maps:
        tskin_map = tskin_preset_maps[export_preset]
        ordered_priority_groups = ordered_priority_maps.get(export_preset, [])
        
        all_priority_weights = set()
        for group in ordered_priority_groups:
            all_priority_weights.update(group)

        print(f" > Applying TSKIN preset for '{export_preset}' based on vertex weights...")

        for i, tri in enumerate(faces_raw):
            applied_tskin = False
            
            if ordered_priority_groups:
                for priority_group in ordered_priority_groups:
                    for v_index in tri.vertices:
                        weight_val = vertex_skins[v_index] if v_index < len(vertex_skins) else 0
                        if weight_val in priority_group:
                            face_tskins[i] = tskin_map[weight_val]
                            applied_tskin = True
                            break
                    if applied_tskin:
                        break
            
            if not applied_tskin:
                for v_index in tri.vertices:
                    weight_val = vertex_skins[v_index] if v_index < len(vertex_skins) else 0
                    if weight_val in tskin_map and weight_val not in all_priority_weights:
                        face_tskins[i] = tskin_map[weight_val]
                        break

        print(f" > Applied TSKIN values to {num_faces} faces based on weight mapping.")
        
    else:
        print(f" > No TSKIN preset defined for '{export_preset}'. Skipping TSKIN data.")
    
    has_tskins = not drop_mode and any(face_tskins)
    
    # ============================ ALPHA LOGIC ============================
    has_alpha = False
    face_alphas = [255] * num_faces
    print(" > Checking for transparent materials...")
    
    mat_alpha_cache = {}
    if obj.data.materials:
        for mat in obj.data.materials:
            if not mat:
                mat_alpha_cache[mat.name if mat else None] = (False, 255)
                continue
            
            is_alpha_mat = mat.blend_method != 'OPAQUE'
            alpha_val = 255
            
            if is_alpha_mat and mat.use_nodes:
                bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                if bsdf:
                    alpha_input = bsdf.inputs.get('Alpha')
                    if alpha_input:
                        alpha_float = alpha_input.default_value
                        alpha_val = int(round((1.0 - alpha_float) * 255))
            
            mat_alpha_cache[mat.name] = (is_alpha_mat, alpha_val)

    for i, tri in enumerate(faces_raw):
        mat = obj.data.materials[tri.material_index] if obj.data.materials and tri.material_index < len(obj.data.materials) else None
        mat_name = mat.name if mat else None
        
        is_alpha_mat, alpha_val = mat_alpha_cache.get(mat_name, (False, 255))
        
        if is_alpha_mat and alpha_val < 255:
            face_alphas[i] = alpha_val
            has_alpha = True
    
    if has_alpha:
        print(f" > Found materials with alpha. Alpha data will be included.")
    else:
        print(" > No alpha detected. Skipping alpha data.")

    # --- 2. BUILD BINARY DATA BLOCKS ---
    print("[2] BUILDING BINARY BLOCKS:")
    
    vert_dirs_data, x_data, y_data, z_data = bytearray(), bytearray(), bytearray(), bytearray()
    last_x, last_y, last_z = 0, 0, 0
    for v_co in vertices_raw:
        vx, vy, vz = int(v_co.x), int(-v_co.z), int(v_co.y)
        dx, dy, dz = vx - last_x, vy - last_y, vz - last_z
        flag = (1 if dx != 0 else 0) | (2 if dy != 0 else 0) | (4 if dz != 0 else 0)
        vert_dirs_data.append(flag)
        if flag & 1: x_data += pack_smart_int(dx)
        if flag & 2: y_data += pack_smart_int(dy)
        if flag & 4: z_data += pack_smart_int(dz)
        last_x, last_y, last_z = vx, vy, vz
        
    face_types_data, face_indices_raw = bytearray(), []
    v1, v2, v3 = 0, 0, 0
    for tri in faces_raw:
        p1, p2, p3 = tri.vertices
        if (v1, v2) == (p2, p1): face_types_data.append(4); face_indices_raw.append(p3); v1, v2, v3 = v2, v1, p3
        elif p1 == v3 and p2 == v2: face_types_data.append(3); face_indices_raw.append(p3); v1, v2, v3 = v3, v2, p3
        elif p1 == v1 and p2 == v3: face_types_data.append(2); face_indices_raw.append(p3); v1, v2, v3 = v1, v3, p3
        else: face_types_data.append(1); face_indices_raw.extend([p1, p2, p3]); v1, v2, v3 = p1, p2, p3
        
    face_indices_data = bytearray()
    last_v = 0
    for index in face_indices_raw:
        face_indices_data += pack_smart_int(index - last_v)
        last_v = index
        
    face_priorities_data = bytes(face_priorities)
    face_tskins_data = bytes(face_tskins)
    vertex_skins_data = bytes(vertex_skins)
    face_alphas_data = bytes(face_alphas)
    face_colors_data = b"".join(pack_word(c) for c in face_colors_hsl)
    face_textures_data = bytes(face_textures)
    texture_coords_data = b"".join(pack_word(idx) for pmn_tuple in texture_triangles for idx in pmn_tuple)

    # --- 3. FINAL ASSEMBLY ---
    print("[3] FINAL ASSEMBLY & WRITE:")
    all_data = vert_dirs_data + face_types_data
    if has_priorities: all_data += face_priorities_data
    if has_tskins: all_data += face_tskins_data
    if has_textures: all_data += face_textures_data
    if has_vertex_skins: all_data += vertex_skins_data
    if has_alpha: all_data += face_alphas_data
    all_data += face_indices_data + face_colors_data
    if has_textures: all_data += texture_coords_data
    all_data += x_data + y_data + z_data
    
    footer = bytearray()
    footer += pack_word(num_vertices)
    footer += pack_word(num_faces)
    footer += struct.pack('B', num_tex_triangles)
    footer += (b'\x01' if has_textures else b'\x00')
    footer += b'\xff' if has_priorities else b'\x01'
    footer += (b'\x01' if has_alpha else b'\x00')
    footer += (b'\x01' if has_tskins else b'\x00')
    footer += (b'\x01' if has_vertex_skins else b'\x00')
    footer += pack_word(len(x_data))
    footer += pack_word(len(y_data))
    footer += pack_word(len(z_data))
    footer += pack_word(len(face_indices_data))
    
    print(f" > Final File Size: {len(all_data) + len(footer)} bytes")
    print(f" > Has Alpha: {has_alpha}, Has TSKINs: {has_tskins}")
    
    with open(filepath, 'wb') as f:
        f.write(all_data)
        f.write(footer)
        
    eval_obj.to_mesh_clear()
    print(f"--- Export of '{obj.name}' to DatMaker format is complete. ---")

def export_dat(filepath, obj, export_preset='DEFAULT'):
    """Exports the object to the specific DatMaker binary format."""
    if export_preset in DROP_PRESETS:
        print(f"Exporting normal model for {export_preset}...")
        _export_core(filepath, obj, export_preset, drop_mode=False)
        
        drop_filepath = filepath.replace('.dat', '_drop.dat') if filepath.endswith('.dat') else filepath + '_drop.dat'
        print(f"Exporting drop model for {export_preset}...")
        _export_core(drop_filepath, obj, export_preset, drop_mode=True)
    else:
        _export_core(filepath, obj, export_preset, drop_mode=False)