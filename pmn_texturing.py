# <blender_header>
bl_info = {
    "name": "PMN Texturing Tool (Simplified)",
    "author": "Your Name (Updated by Gemini)",
    "version": (3, 6, 0),
    "blender": (3, 0, 0),
    "location": "View3D > UI > RSPS ADDON",
    "description": "A simplified tool for applying textures using a PMN workflow. Now supports multi-material visualization with UV direction arrows.",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}
# </blender_header>
import bpy
import os
import re
import bmesh
import gpu
import blf
import math
import bpy_extras.view3d_utils
import bpy.utils.previews
from gpu_extras.batch import batch_for_shader
from bpy.props import (
    FloatVectorProperty,
    PointerProperty,
    EnumProperty,
    StringProperty,
    BoolProperty,
    FloatProperty,
)
from bpy.types import (
    PropertyGroup,
    Panel,
    Operator,
)
from mathutils import Vector
from bpy.app.handlers import persistent
# ===============================================================
# GLOBAL VARIABLES & SETTINGS
# ===============================================================
preview_collections = {}
uv_state_cache = {} # Cache for automatic PMN updates
pmn_draw_handler = None # Global for the PMN visualization handler
addon_keymaps = [] # Stores custom keymaps for registration/unregistration
# This controls how many times the texture will loop within the timeline.
LOOP_CYCLES = 1.0
# ===============================================================
# CORE LOGIC & HELPER FUNCTIONS
# ===============================================================
def get_mapping_node(material):
    """
    Finds or creates a Mapping node and ensures image textures are set to REPEAT.
    """
    if not (material and material.use_nodes):
        return None
     
    nodes = material.node_tree.nodes
    mapping_node = nodes.get('RS Mapping')
    if not mapping_node:
        mapping_node = next((node for node in nodes if node.type == 'MAPPING'), None)
     
    image_nodes = [node for node in nodes if node.type == 'TEX_IMAGE']
 
    if not mapping_node and image_nodes:
        tex_coord_node = nodes.new(type='ShaderNodeTexCoord')
        mapping_node = nodes.new(type='ShaderNodeMapping')
        mapping_node.name = 'RS Mapping'
     
        ref_loc = image_nodes[0].location
        tex_coord_node.location = ref_loc + Vector((-400, 0))
        mapping_node.location = ref_loc + Vector((-200, 0))
     
        material.node_tree.links.new(tex_coord_node.outputs['UV'], mapping_node.inputs['Vector'])
        print("Created new Texture Coordinate and Mapping nodes.")
        for img_node in image_nodes:
            if not img_node.inputs['Vector'].is_linked:
                material.node_tree.links.new(mapping_node.outputs['Vector'], img_node.inputs['Vector'])
                print(f"Linked new Mapping node to '{img_node.image.name}'.")
 
    for node in image_nodes:
        if node.extension != 'REPEAT':
            node.extension = 'REPEAT'
 
    return mapping_node
def get_texture_dump_path():
    """Constructs the path to the texture_dump folder next to the blend file or script."""
    try:
        addon_dir = os.path.dirname(os.path.realpath(__file__))
    except NameError:
        addon_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else ""
    return os.path.join(addon_dir, "texture_dump")
def natural_sort_key(s):
    """Sorts strings numerically (e.g., 'tex10' comes after 'tex2')."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'([0-9]+)', s)]
def load_textures_for_enum(self, context):
    """Populates the texture list EnumProperty, sorted naturally."""
    items = []
    texture_dir = get_texture_dump_path()
 
    if not os.path.isdir(texture_dir):
        return [("NONE", "Directory Not Found", "Create a 'texture_dump' folder.", 'ERROR', 0)]
     
    supported = ('.png', '.jpg', '.jpeg', '.tga', '.bmp')
    pcoll = preview_collections.get("main")
 
    if not pcoll:
        pcoll = bpy.utils.previews.new()
        preview_collections["main"] = pcoll
 
    try:
        filenames = sorted(os.listdir(texture_dir), key=natural_sort_key)
    except OSError:
        return [("NONE", "Error", "Cannot access the folder.", 'ERROR', 0)]
 
    processed_icons = set(pcoll.keys())
    for i, filename in enumerate(filenames):
        if filename.lower().endswith(supported):
            filepath = os.path.join(texture_dir, filename)
         
            if filename not in processed_icons:
                pcoll.load(filename, filepath, 'IMAGE')
         
            icon = pcoll[filename]
            items.append((filepath, filename, f"Texture: {filename}", icon.icon_id, i))
         
    if not items:
        return [("NONE", "No Textures Found", "No images in 'texture_dump' folder.", 'QUESTION', 0)]
     
    return items
def create_datmaker_uvs(context, obj, operator):
    """Creates a 'Project from View (Bounds)' style UV layout on selected faces."""
    if obj.mode != 'EDIT':
        operator.report({'ERROR'}, "Must be in Edit Mode.")
        return False
     
    bm = bmesh.from_edit_mesh(obj.data)
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.new()
    selected_faces = [f for f in bm.faces if f.select]
 
    if not selected_faces:
        operator.report({'ERROR'}, "No faces are selected in Edit Mode.")
        return False
 
    region = context.region
    rv3d = context.region_data
 
    unique_verts = {loop.vert for face in selected_faces for loop in face.loops}
 
    vert_coords_2d = {}
    for vert in unique_verts:
        screen_co = bpy_extras.view3d_utils.location_3d_to_region_2d(region, rv3d, obj.matrix_world @ vert.co)
        if screen_co:
            vert_coords_2d[vert.index] = screen_co
         
    if not vert_coords_2d:
        operator.report({'ERROR'}, "Could not project vertices to screen space.")
        return False
    min_x = min(co.x for co in vert_coords_2d.values())
    max_x = max(co.x for co in vert_coords_2d.values())
    min_y = min(co.y for co in vert_coords_2d.values())
    max_y = max(co.y for co in vert_coords_2d.values())
 
    width = max_x - min_x
    height = max_y - min_y
 
    if width < 1e-6 or height < 1e-6:
        operator.report({'ERROR'}, "Selected faces have no area in the current view.")
        return False
     
    for face in selected_faces:
        for loop in face.loops:
            if loop.vert.index in vert_coords_2d:
                screen_co = vert_coords_2d[loop.vert.index]
                normalized_x = (screen_co.x - min_x) / width
                normalized_y = (screen_co.y - min_y) / height
                loop[uv_layer].uv = Vector((normalized_x, normalized_y))
             
    bmesh.update_edit_mesh(obj.data)
    return True
def update_pmn_from_uvs(context, operator=None):
    """
    Calculates P, M, and N world coordinates from the bounding box of the selected UVs.
    This version correctly handles rotated, scaled, and translated UV islands.
    """
    def report(msg_type, text):
        if operator:
            operator.report({msg_type}, text)
        else:
            print(f"PMN Update: [{msg_type}] {text}")
    obj = context.active_object
    mat = obj.active_material
    if not (mat and hasattr(mat, 'rs_pmn_mat')):
        report('ERROR', "Active object has no compatible PMN material.")
        return False
     
    if obj.mode != 'EDIT':
        report('ERROR', "Must be in Edit Mode.")
        return False
     
    bm = bmesh.from_edit_mesh(obj.data)
    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        report('ERROR', "No active UV map found.")
        return False
 
    selected_faces = [f for f in bm.faces if f.select]
    if not selected_faces:
        report('ERROR', "No faces are selected in Edit Mode.")
        return False
    selected_loops = [l for f in selected_faces for l in f.loops]
    if not selected_loops:
        report('ERROR', "Selected faces have no loops.")
        return False
    all_uvs = [l[uv_layer].uv for l in selected_loops]
    min_u = min(uv.x for uv in all_uvs)
    max_u = max(uv.x for uv in all_uvs)
    min_v = min(uv.y for uv in all_uvs)
    max_v = max(uv.y for uv in all_uvs)
 
    targets = {
        'p': Vector((min_u, max_v)), # Top-left
        'm': Vector((max_u, max_v)), # Top-right
        'n': Vector((min_u, min_v)), # Bottom-left
    }
    pos_dict = {}
    for key, target_uv in targets.items():
        min_dist_sq = float('inf')
        closest_loop = None
        for loop in selected_loops:
            dist_sq = (loop[uv_layer].uv - target_uv).length_squared
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_loop = loop
             
        if closest_loop:
            pos_dict[key] = closest_loop.vert.co # Store local coordinates
 
    if len(pos_dict) < 3:
        report('WARNING', "Could not determine all three PMN positions from the UV corners.")
        return False
 
    p, m, n = Vector(pos_dict['p']), Vector(pos_dict['m']), Vector(pos_dict['n'])
    v_pm = m - p
    v_pn = n - p
    if v_pm.cross(v_pn).length_squared < 1e-9:
        report('WARNING', "Calculated PMN triangle is degenerate (a line or point). Check your 3D mesh and UV layout.")
        return False
    pmn_props = mat.rs_pmn_mat
    pmn_props.p = p
    pmn_props.m = m
    pmn_props.n = n
 
    return True
def pmn_to_uv(a, b, c, p, m, n):
    """Converts three world-space triangle vertices (a,b,c) to UV coordinates based on PMN."""
    f1 = m - p
    f2 = n - p
 
    det = f1.dot(f1) * f2.dot(f2) - f1.dot(f2)**2
    if abs(det) < 1e-9: return Vector((0,0)), Vector((0,0)), Vector((0,0))
 
    inv_det = 1.0 / det
 
    inv00 = f2.dot(f2) * inv_det
    inv01 = -f1.dot(f2) * inv_det
    inv10 = -f1.dot(f2) * inv_det
    inv11 = f1.dot(f1) * inv_det
 
    def transform(v_proj):
        return Vector((inv00 * v_proj[0] + inv01 * v_proj[1],
                       inv10 * v_proj[0] + inv11 * v_proj[1]))
 
    proj_a = Vector((f1.dot(a - p), f2.dot(a - p)))
    proj_b = Vector((f1.dot(b - p), f2.dot(b - p)))
    proj_c = Vector((f1.dot(c - p), f2.dot(c - p)))
 
    return transform(proj_a), transform(proj_b), transform(proj_c)
def update_uvs_from_pmn(context, operator=None):
    """Updates the UV map of selected faces from the material's PMN coordinates."""
    def report(msg_type, text):
        if operator:
            operator.report({msg_type}, text)
        else:
            print(f"UV Update: [{msg_type}] {text}")
    obj = context.active_object
    mat = obj.active_material
    if not mat or not hasattr(mat, 'rs_pmn_mat'):
        report('ERROR', "No active PMN material.")
        return False
    p_local = Vector(mat.rs_pmn_mat.p)
    m_local = Vector(mat.rs_pmn_mat.m)
    n_local = Vector(mat.rs_pmn_mat.n)
    p = obj.matrix_world @ p_local
    m = obj.matrix_world @ m_local
    n = obj.matrix_world @ n_local
 
    if (m - p).length_squared < 1e-9 or (n - p).length_squared < 1e-9:
        report('WARNING', "PMN coordinates are not properly defined. Cannot update UVs.")
        return False
    bm = bmesh.from_edit_mesh(obj.data)
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.new()
 
    selected_faces = [f for f in bm.faces if f.select]
    if not selected_faces:
        report('ERROR', "No faces selected.")
        return False
     
    pmn_props = mat.rs_pmn_mat
    for face in selected_faces:
        if len(face.loops) == 3:
            verts = [obj.matrix_world @ loop.vert.co for loop in face.loops]
            uv_coords = pmn_to_uv(verts[0], verts[1], verts[2], p, m, n)
         
            for i in range(3):
                face.loops[i][uv_layer].uv = uv_coords[i]
          
            # Apply saved UV transform (scale and offset)
            # Removed to prevent unwanted scaling/flipping/position changes
            # for i in range(3):
            #     face.loops[i][uv_layer].uv.x = pmn_props.offset_u + face.loops[i][uv_layer].uv.x * pmn_props.scale_u
            #     face.loops[i][uv_layer].uv.y = pmn_props.offset_v + face.loops[i][uv_layer].uv.y * pmn_props.scale_v
 
    bmesh.update_edit_mesh(obj.data)
    return True
# ===============================================================
# AUTOMATIC UPDATE HANDLER
# ===============================================================
@persistent
def pmn_depsgraph_handler(scene):
    """Automatically updates PMN coordinates when UVs change in Edit Mode."""
    context = bpy.context
    obj = context.active_object
 
    if not (obj and obj.type == 'MESH' and obj.mode == 'EDIT'):
        if obj and obj.name in uv_state_cache:
            del uv_state_cache[obj.name]
        return
     
    mat = obj.active_material
    if not (mat and hasattr(mat, 'rs_pmn_mat')):
        return
    try:
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        if not uv_layer: return
     
        selected_faces = [f for f in bm.faces if f.select]
        if not selected_faces:
            if obj.name in uv_state_cache:
                del uv_state_cache[obj.name]
            return
     
        current_uvs = tuple(loop[uv_layer].uv[i] for face in selected_faces for loop in face.loops for i in range(2))
        last_uvs = uv_state_cache.get(obj.name)
     
        if current_uvs != last_uvs:
            if update_pmn_from_uvs(context, operator=None):
                uv_state_cache[obj.name] = current_uvs
    except Exception:
        if obj and obj.name in uv_state_cache:
            del uv_state_cache[obj.name]
# ===============================================================
# PMN VISUALIZATION DRAW HANDLER (MODIFIED)
# ===============================================================
def draw_pmn_visualization(self, context):
    """Draws the PMN triangles and UV direction arrows for ALL PMN materials on the active object."""
    obj = context.active_object
 
    if not (obj and obj.type == 'MESH' and obj.mode in ['EDIT', 'OBJECT']):
        return
    region = context.region
    rv3d = context.region_data
    font_id = 0 # Use default font ID 0 instead of loading "default"
 
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.line_width_set(2.0)
    gpu.state.point_size_set(5.0)
    blf.size(font_id, 16)
 
    # Get the view vector to help orient arrowheads correctly
    view_vector = rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))
    def create_arrow_verts(start, end, head_ratio=0.25, head_angle_deg=30):
        """Helper function to generate vertices for a 3D arrow."""
        direction = end - start
        arrow_len = direction.length
        if arrow_len < 1e-6:
            return []
     
        direction.normalize()
        head_len = arrow_len * head_ratio
        # Find a robust perpendicular vector for the arrowhead orientation
        # If the arrow direction is parallel to the view direction, use view's X-axis
        if abs(direction.dot(view_vector)) > 0.99:
            side_vector = rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
        else:
            side_vector = view_vector
        perp_vec = direction.cross(side_vector).normalized()
     
        head_base = end - direction * head_len
        head_width = head_len * math.tan(math.radians(head_angle_deg))
     
        pt1 = head_base + perp_vec * head_width
        pt2 = head_base - perp_vec * head_width
     
        # Returns vertex pairs for drawing lines: shaft, head_side_1, head_side_2
        return [start, end, end, pt1, end, pt2]
    for mat_slot in obj.material_slots:
        mat = mat_slot.material
     
        if not (mat and hasattr(mat, 'rs_pmn_mat')):
            continue
        pmn_props = mat.rs_pmn_mat
        p_local, m_local, n_local = Vector(pmn_props.p), Vector(pmn_props.m), Vector(pmn_props.n)
        p = obj.matrix_world @ p_local
        m = obj.matrix_world @ m_local
        n = obj.matrix_world @ n_local
     
        if p_local.length_squared < 1e-6 and m_local.length_squared < 1e-6 and n_local.length_squared < 1e-6:
            continue
         
        mapping_node = get_mapping_node(mat)
        color = (*mat.diffuse_color[:3], 1.0) if mat.diffuse_color else (1.0, 0.7, 0.1, 1.0)
        shader.uniform_float("color", color)
     
        # --- Draw PMN Triangle (White for visibility in both modes) ---
        white_color = (1.0, 1.0, 1.0, 1.0)
        shader.uniform_float("color", white_color)
        batch_lines = batch_for_shader(shader, 'LINES', {"pos": [p, m, m, n, n, p]})
        batch_lines.draw(shader)
        batch_points = batch_for_shader(shader, 'POINTS', {"pos": [p, m, n]})
        batch_points.draw(shader)
     
        # --- Draw Single UV Direction Arrow (Green, U direction from center) ---
        center = (p + m + n) / 3.0
        u_vec = m - p
     
        # Calculate a sensible length for the arrow based on the triangle size
        arrow_scale = u_vec.length * 0.4 if u_vec.length > 1e-6 else 1.0
     
        arrow_verts = []
        if u_vec.length > 1e-6:
            u_end = center + u_vec.normalized() * arrow_scale
            arrow_verts = create_arrow_verts(center, u_end)
     
        if arrow_verts:
            gpu.state.line_width_set(1.5) # Make arrow slightly thinner
            arrow_color = (0.0, 1.0, 0.0, 0.9) # Green color for arrow
            shader.uniform_float("color", arrow_color)
            batch_arrow = batch_for_shader(shader, 'LINES', {"pos": arrow_verts})
            batch_arrow.draw(shader)
            gpu.state.line_width_set(2.0) # Reset line width
     
        # --- Draw Animation Direction Arrow if driver present ---
        if mapping_node and mat.use_nodes and mat.node_tree and mat.node_tree.animation_data:
            has_driver = False
            sign = 1.0
            movement_dir = None
            for driver in mat.node_tree.animation_data.drivers:
                if (driver.data_path == f'nodes["{mapping_node.name}"].inputs[1].default_value' and
                    driver.array_index == 1):
                    has_driver = True
                    expr = driver.driver.expression
                    # Parse sign from expression like "1.0 * (fmod..." or "-1.0 * (fmod..."
                    match = re.search(r'^([+-]?\d*\.?\d*)\s*\*\s*\(', expr)
                    if match:
                        sign_str = match.group(1)
                        sign = float(sign_str) if sign_str else 1.0
                    v_vec = n - p
                    if v_vec.length > 1e-6:
                        movement_dir = v_vec.normalized() * sign
                    break
            if has_driver and movement_dir and movement_dir.length > 1e-6:
                v_arrow_scale = (n - p).length * 0.4
                anim_end = center + movement_dir * v_arrow_scale
                anim_verts = create_arrow_verts(center, anim_end)
                if anim_verts:
                    gpu.state.line_width_set(1.5)
                    anim_color = (1.0, 0.0, 0.0, 0.9) # Red color for animation direction
                    shader.uniform_float("color", anim_color)
                    batch_anim = batch_for_shader(shader, 'LINES', {"pos": anim_verts})
                    batch_anim.draw(shader)
                    gpu.state.line_width_set(2.0)
        # --- Draw Text Labels ---
        blf.color(font_id, *color)
        for pos, text in zip([p, m, n], ["P", "M", "N"]):
            coord_2d = bpy_extras.view3d_utils.location_3d_to_region_2d(region, rv3d, pos)
            if coord_2d:
                blf.position(font_id, coord_2d.x + 10, coord_2d.y + 10, 0)
                blf.draw(font_id, text)
# ===============================================================
# PROPERTY GROUPS & OPERATORS
# ===============================================================
class RS_Material_PropertyGroup(PropertyGroup):
    """Stores the P, M, N world coordinates per material."""
    p: FloatVectorProperty(name="P (Origin)", subtype='XYZ', size=3, precision=4)
    m: FloatVectorProperty(name="M (U-Vector)", subtype='XYZ', size=3, precision=4)
    n: FloatVectorProperty(name="N (V-Vector)", subtype='XYZ', size=3, precision=4)
    offset_u: FloatProperty(name="Offset U", default=0.0, precision=4)
    offset_v: FloatProperty(name="Offset V", default=0.0, precision=4)
    scale_u: FloatProperty(name="Scale U", default=1.0, precision=4)
    scale_v: FloatProperty(name="Scale V", default=1.0, precision=4)
class RS_Scene_PropertyGroup(PropertyGroup):
    """Stores scene-level properties for the addon."""
    texture_list: EnumProperty(name="Texture", items=load_textures_for_enum)
    show_pmn_visualization: BoolProperty(
        name="Show Tex Triangle (PMN)",
        description="Toggle visualization of the PMN triangle and UV arrows",
        default=False,
        update=lambda self, context: toggle_pmn_visualization(context)
    )
    auto_sync_enabled: BoolProperty(
        name="Enable Auto Sync",
        description="Automatically sync PMN and UVs when switching between Object and Edit modes",
        default=False
    )
def toggle_pmn_visualization(context):
    """Adds or removes the PMN drawing handler."""
    global pmn_draw_handler
    if pmn_draw_handler:
        bpy.types.SpaceView3D.draw_handler_remove(pmn_draw_handler, 'WINDOW')
        pmn_draw_handler = None
     
    if context.scene.rs_pmn.show_pmn_visualization:
        pmn_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_pmn_visualization, (None, context), 'WINDOW', 'POST_VIEW'
        )
 
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()
class RS_OT_ApplyTexture(Operator):
    bl_idname = "rs_pmn.apply_texture"
    bl_label = "Apply Texture & Create UVs"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        obj, rs_props = context.active_object, context.scene.rs_pmn
        if not (obj and obj.type == 'MESH' and obj.mode == 'EDIT'):
            self.report({'ERROR'}, "Select a mesh and enter Edit Mode.")
            return {'CANCELLED'}
         
        if rs_props.texture_list in {"", "NONE"}:
            self.report({'ERROR'}, "Please select a valid texture from the list.")
            return {'CANCELLED'}
        image = bpy.data.images.load(rs_props.texture_list, check_existing=True)
        mat_name = f"PMN_{os.path.basename(image.name)}"
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            nodes, links = mat.node_tree.nodes, mat.node_tree.links
            nodes.clear()
         
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            output = nodes.new('ShaderNodeOutputMaterial')
            tex_node = nodes.new('ShaderNodeTexImage')
            tex_node.image = image
         
            links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
            links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
            bsdf.inputs['Roughness'].default_value = 1.0
        if mat.name not in obj.data.materials:
            obj.data.materials.append(mat)
         
        obj.active_material_index = obj.data.materials.find(mat.name)
        bpy.ops.object.material_slot_assign()
        if create_datmaker_uvs(context, obj, self):
            if update_pmn_from_uvs(context, self):
                self.report({'INFO'}, f"Applied '{mat.name}' and calculated PMN.")
            else:
                self.report({'WARNING'}, f"Applied '{mat.name}' but failed to set PMN. Check UVs.")
        else:
            self.report({'WARNING'}, f"Applied '{mat.name}' but failed to create UVs.")
     
        return {'FINISHED'}
class RS_OT_ApplyMultiTexture(Operator):
    bl_idname = "rs_pmn.apply_multi_texture"
    bl_label = "Apply Textures Multi Texturing"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        obj, rs_props = context.active_object, context.scene.rs_pmn
        if not (obj and obj.type == 'MESH' and obj.mode == 'EDIT'):
            self.report({'ERROR'}, "Select a mesh and enter Edit Mode.")
            return {'CANCELLED'}
         
        if rs_props.texture_list in {"", "NONE"}:
            self.report({'ERROR'}, "Please select a valid texture from the list.")
            return {'CANCELLED'}
        image = bpy.data.images.load(rs_props.texture_list, check_existing=True)
        mat_name = f"PMN_{os.path.basename(image.name)}"
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        nodes.clear()
     
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        output = nodes.new('ShaderNodeOutputMaterial')
        tex_node = nodes.new('ShaderNodeTexImage')
        tex_node.image = image
     
        links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        bsdf.inputs['Roughness'].default_value = 1.0
     
        if mat.name not in obj.data.materials:
            obj.data.materials.append(mat)
         
        obj.active_material_index = obj.data.materials.find(mat.name)
        bpy.ops.object.material_slot_assign()
        if create_datmaker_uvs(context, obj, self):
            if update_pmn_from_uvs(context, self):
                self.report({'INFO'}, f"Applied multi '{mat.name}' and calculated PMN.")
            else:
                self.report({'WARNING'}, f"Applied multi '{mat.name}' but failed to set PMN. Check UVs.")
        else:
            self.report({'WARNING'}, f"Applied multi '{mat.name}' but failed to create UVs.")
     
        return {'FINISHED'}
class RS_OT_SyncPMNandUV(Operator):
    bl_idname = "rs_pmn.sync_pmn_uv"
    bl_label = "Update PMN from UV"
    bl_description = "Updates PMN from UVs only (no UV normalization)"
    bl_options = {'REGISTER', 'UNDO'}
 
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and obj.mode == 'EDIT' and obj.active_material)
    def execute(self, context):
        if not update_pmn_from_uvs(context, self):
            return {'CANCELLED'}
        # Removed UV update to prevent restoration/normalization
        # if not update_uvs_from_pmn(context, self):
        #     return {'CANCELLED'}
        self.report({'INFO'}, "Updated PMN from UVs.")
        return {'FINISHED'}
class RS_OT_CaptureUVTransform(Operator):
    bl_idname = "rs_pmn.capture_uv_transform"
    bl_label = "Capture UV Transform"
    bl_options = {'REGISTER', 'UNDO'}
 
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH' and obj.active_material and hasattr(obj.active_material, 'rs_pmn_mat'))
 
    def execute(self, context):
        obj = context.active_object
        mat = obj.active_material
        pmn_props = mat.rs_pmn_mat
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        if not uv_layer:
            self.report({'ERROR'}, "No UV layer.")
            return {'CANCELLED'}
     
        selected_faces = [f for f in bm.faces if f.select]
        if not selected_faces:
            self.report({'ERROR'}, "No faces selected.")
            return {'CANCELLED'}
     
        selected_loops = [l for f in selected_faces for l in f.loops]
        all_uvs = [l[uv_layer].uv for l in selected_loops]
        if not all_uvs:
            self.report({'ERROR'}, "No UVs.")
            return {'CANCELLED'}
     
        min_u = min(uv.x for uv in all_uvs)
        max_u = max(uv.x for uv in all_uvs)
        min_v = min(uv.y for uv in all_uvs)
        max_v = max(uv.y for uv in all_uvs)
     
        scale_u = max_u - min_u if max_u > min_u else 1.0
        scale_v = max_v - min_v if max_v > min_v else 1.0
     
        pmn_props.offset_u = min_u
        pmn_props.offset_v = min_v
        pmn_props.scale_u = scale_u
        pmn_props.scale_v = scale_v
     
        self.report({'INFO'}, f"Captured: Offset U/V: {min_u:.3f}/{min_v:.3f}, Scale U/V: {scale_u:.3f}/{scale_v:.3f}")
        return {'FINISHED'}
class RS_OT_ToggleAutoSync(Operator):
    bl_idname = "rs_pmn.toggle_auto_sync"
    bl_label = "Toggle Auto Sync PMN"
    bl_description = "Automatically syncs PMN and UVs on mode change"
    def execute(self, context):
        rs_props = context.scene.rs_pmn
        if rs_props.auto_sync_enabled:
            # The running modal will see this property change to False and cancel itself.
            rs_props.auto_sync_enabled = False
        else:
            # This will start the modal operator, which will in turn set the property to True.
            bpy.ops.wm.modal_mode_watcher('INVOKE_DEFAULT')
        return {'FINISHED'}
### --- ANIMATION OPERATORS RE-ADDED --- ###
class RS_OT_AddSeamlessLoopDriver(Operator):
    bl_idname = "rs_pmn.add_seamless_loop_driver"
    bl_label = "Add Seamless Loop Driver"
    bl_options = {'REGISTER', 'UNDO'}
 
    axis: StringProperty(name="Axis", default="VERTICAL")
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and obj.mode == 'EDIT' and obj.active_material)
    def execute(self, context):
        # Removed UV flipping to prevent unwanted flips
        # bm = bmesh.from_edit_mesh(context.active_object.data)
        # uv_layer = bm.loops.layers.uv.active
        # if not uv_layer:
        #     self.report({'ERROR'}, "No active UV map found.")
        #     return {'CANCELLED'}
        #  
        # selected_faces = [f for f in bm.faces if f.select]
        # if not selected_faces:
        #     self.report({'ERROR'}, "No faces selected.")
        #     return {'CANCELLED'}
        # if self.axis == "VERTICAL":
        #     for face in selected_faces:
        #         for loop in face.loops:
        #             loop[uv_layer].uv.y = 1.0 - loop[uv_layer].uv.y
        #     direction_index, sign = 1, 1.0 # Animate Y axis, positive (moves texture down)
        # else: # This operator will only be called for Vertical, but keep for completeness
        #     return {'CANCELLED'}
        #  
        # bmesh.update_edit_mesh(context.active_object.data)
        # update_pmn_from_uvs(context, self)
        direction_index, sign = 1, 1.0 # Animate Y axis, positive (moves texture down)
     
        mapping_node = get_mapping_node(context.active_object.active_material)
        if not mapping_node:
            self.report({'ERROR'}, "Could not find or create a Mapping node.")
            return {'CANCELLED'}
         
        scene = context.scene
        start_frame, end_frame = scene.frame_start, scene.frame_end
        if start_frame >= end_frame:
            self.report({'ERROR'}, "Scene end frame must be after the start frame.")
            return {'CANCELLED'}
     
        duration = end_frame - start_frame
        location_socket = mapping_node.inputs['Location']
     
        try: location_socket.driver_remove("default_value")
        except (TypeError, RuntimeError): pass
     
        fcurve = location_socket.driver_add("default_value", direction_index)
        expression = f"fmod(((frame - {start_frame}) / {duration}) * {LOOP_CYCLES}, {LOOP_CYCLES})"
        fcurve.driver.expression = f"{sign} * ({expression})"
        self.report({'INFO'}, "Added seamless driver for 'VERTICAL' axis.")
        return {'FINISHED'}
class RS_OT_RemoveTextureDrivers(Operator):
    bl_idname = "rs_pmn.remove_texture_drivers"
    bl_label = "Stop Animation"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        obj = context.active_object
        if not (obj and obj.active_material):
            self.report({'ERROR'}, "Active object must have a material.")
            return {'CANCELLED'}
         
        mapping_node = get_mapping_node(obj.active_material)
        if not mapping_node:
            self.report({'INFO'}, "No Mapping node found to remove drivers from.")
            return {'CANCELLED'}
         
        try:
            mapping_node.inputs['Location'].driver_remove("default_value")
            mapping_node.inputs['Location'].default_value = (0, 0, 0)
            self.report({'INFO'}, "Removed drivers and reset texture location.")
        except (TypeError, RuntimeError):
            self.report({'INFO'}, "No drivers were found to remove.")
     
        return {'FINISHED'}
# ===============================================================
# UI PANEL
# ===============================================================
class RS_Panel_Main(Panel):
    bl_label = "Texture Tool"
    bl_idname = "OBJECT_PT_rs_pmn_texturing"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RSPS ADDON"
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        rs_props = context.scene.rs_pmn
 
        layout.label(text="Step 1: Select Texture", icon='TEXTURE')
        box = layout.box()
        box.prop(rs_props, "texture_list", text="")
 
        layout.label(text="Step 2: Apply to Faces", icon='EDITMODE_HLT')
        box = layout.box()
        col = box.column()
        col.enabled = obj is not None and obj.type == 'MESH' and obj.mode == 'EDIT'
        col.operator("rs_pmn.apply_texture", text="Apply Texture & Create UVs")
        col.operator("rs_pmn.apply_multi_texture", text="Apply Textures Multi Texturing")
 
        layout.label(text="Step 3: Adjust & Animate", icon='TOOL_SETTINGS')
        main_box = layout.box()
        active_mat = obj.active_material if obj else None
        has_pmn_mat = active_mat and hasattr(active_mat, 'rs_pmn_mat')
        if not has_pmn_mat:
            main_box.enabled = False
            main_box.label(text="Apply a texture to enable options.", icon='INFO')
            return
         
        update_box = main_box.box()
        update_col = update_box.column()
        update_col.label(text="Coordinates:", icon='UV_SYNC_SELECT')
     
        # Auto Sync Toggle Button
        text = "Stop Auto Sync" if rs_props.auto_sync_enabled else "Start Auto Sync"
        icon = 'PAUSE' if rs_props.auto_sync_enabled else 'PLAY'
        update_col.operator("rs_pmn.toggle_auto_sync", text=text, icon=icon)
     
        # Manual Sync Button
        manual_sync_row = update_col.row()
        manual_sync_row.enabled = context.mode == 'EDIT_MESH'
        manual_sync_row.operator("rs_pmn.sync_pmn_uv", text="Manual Sync (Current Selection)")
        if context.mode != 'EDIT_MESH':
             update_col.label(text="Enter Edit Mode for manual sync.", icon='INFO')
     
        # UV Transform Section
        transform_box = main_box.box()
        transform_col = transform_box.column()
        transform_col.enabled = context.mode == 'EDIT_MESH'
        transform_col.label(text="UV Transform:", icon='EMPTY_AXIS')
        pmn_props = active_mat.rs_pmn_mat
        row = transform_col.row()
        row.prop(pmn_props, "offset_u")
        row.prop(pmn_props, "offset_v")
        row = transform_col.row()
        row.prop(pmn_props, "scale_u")
        row.prop(pmn_props, "scale_v")
        transform_col.operator("rs_pmn.capture_uv_transform", text="Capture Current")
     
        # --- ANIMATION SECTION RE-ADDED ---
        anim_box = main_box.box()
        anim_box.label(text="Animation:", icon='ACTION')
        anim_box.enabled = context.mode == 'EDIT_MESH'
     
        col = anim_box.column(align=True)
        op = col.operator("rs_pmn.add_seamless_loop_driver", text="↕ Animate Vertically")
        op.axis = "VERTICAL"
     
        col.operator("rs_pmn.remove_texture_drivers", text="Stop Animation", icon='X')
        vis_box = main_box.box()
        vis_box.label(text="Visualization", icon='VIEWZOOM')
        vis_box.prop(rs_props, "show_pmn_visualization", toggle=True)
# ===============================================================
# REGISTRATION
# ===============================================================
classes = (
    RS_Material_PropertyGroup,
    RS_Scene_PropertyGroup,
    RS_OT_ApplyTexture,
    RS_OT_ApplyMultiTexture,
    RS_OT_SyncPMNandUV,
    RS_OT_CaptureUVTransform,
    RS_OT_ToggleAutoSync, # Added the new operator
    RS_OT_AddSeamlessLoopDriver,
    RS_OT_RemoveTextureDrivers,
    RS_Panel_Main,
)
def register():
    global preview_collections
 
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
 
    for cls in classes:
        bpy.utils.register_class(cls)
 
    bpy.types.Material.rs_pmn_mat = PointerProperty(type=RS_Material_PropertyGroup)
    bpy.types.Scene.rs_pmn = PointerProperty(type=RS_Scene_PropertyGroup)
 
    if pmn_depsgraph_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(pmn_depsgraph_handler)
def unregister():
    global pmn_draw_handler
 
    if pmn_depsgraph_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(pmn_depsgraph_handler)
     
    if pmn_draw_handler:
        bpy.types.SpaceView3D.draw_handler_remove(pmn_draw_handler, 'WINDOW')
        pmn_draw_handler = None
     
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
 
    try: del bpy.types.Scene.rs_pmn
    except AttributeError: pass
 
    try: del bpy.types.Material.rs_pmn_mat
    except AttributeError: pass
 
    for cls in reversed(classes):
        try: bpy.utils.unregister_class(cls)
        except RuntimeError: pass
if __name__ == "__main__":
    register()