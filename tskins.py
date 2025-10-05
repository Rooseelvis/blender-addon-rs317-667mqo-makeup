# tskins.py
import bpy
import bmesh
import re
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Vector
from . import materials as material_data  # Import the material data

# --- Global Cache for Parsed Colors ---
PARSED_MATERIALS = None

# --- Helper Functions ---

def parse_material_colors():
    """
    Parses the string-based material data into a list of color tuples.
    This only runs once and caches the result for performance.
    """
    global PARSED_MATERIALS
    if PARSED_MATERIALS is not None:
        return PARSED_MATERIALS

    print("DEBUG: Parsing material colors from materials.py...")
    parsed_colors = [(0.5, 0.5, 0.5, 1.0)] * 256  # Default gray
    
    # Regex to find the col(R G B A) part of the string
    color_regex = re.compile(r"col\(([\d\.]+) ([\d\.]+) ([\d\.]+) ([\d\.]+)\)")
    for i, mat_string in enumerate(material_data.MATERIALS):
        if i >= 256: 
            break
        match = color_regex.search(mat_string)
        if match:
            r, g, b, a = [float(val) for val in match.groups()]
            parsed_colors[i] = (r, g, b, a)
    
    PARSED_MATERIALS = parsed_colors
    print(f"DEBUG: Successfully parsed {len(PARSED_MATERIALS)} colors.")
    return PARSED_MATERIALS

def triangulate_face_indices(face):
    """Simple fan triangulation for the face."""
    if len(face.verts) == 3:
        return [tuple(v.index for v in face.verts)]
    tris = []
    for i in range(1, len(face.verts) - 1):
        tris.append((face.verts[0].index, face.verts[i].index, face.verts[i + 1].index))
    return tris

# --- Visualization Draw Handlers ---

def draw_tskin_overlay(context):
    """Draws the colored overlay on faces based on their TSKIN data for selected mesh objects."""
    alpha = context.scene.rsps_tskin_alpha
    if alpha <= 0.0:
        return

    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']

    if not selected_meshes:
        return

    # Ensure colors are parsed and ready
    colors = parse_material_colors()
    
    # Store original GPU states to restore them later
    original_depth_test = gpu.state.depth_test_get()
    original_blend = gpu.state.blend_get()

    try:
        gpu.state.depth_test_set('NONE')
        gpu.state.blend_set('ALPHA')
        gpu.state.face_culling_set('BACK')

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Precompute data for all objects
        obj_data = {}
        all_tskins = set()
        for obj in selected_meshes:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            if not obj.data.vertex_colors:
                bm.free()
                continue

            tskin_layer = bm.loops.layers.color.get('RSTSKIN')
            if not tskin_layer:
                bm.free()
                continue

            verts_3d = [obj.matrix_world @ v.co for v in bm.verts]
            
            faces_by_tskin = {}
            for face in bm.faces:
                tskin = int(face.loops[0][tskin_layer][0] * 255)
                if tskin not in faces_by_tskin:
                    faces_by_tskin[tskin] = []
                
                tris = triangulate_face_indices(face)
                faces_by_tskin[tskin].extend(tris)

            if faces_by_tskin:
                obj_data[obj] = {
                    'bm': bm,
                    'verts_3d': verts_3d,
                    'faces_by_tskin': faces_by_tskin
                }
                all_tskins.update(faces_by_tskin.keys())

        if not obj_data:
            return

        # Sort tskins ascending: draw lower first
        sorted_tskins = sorted(all_tskins)

        for tskin in sorted_tskins:
            for obj, data in obj_data.items():
                tris_list = data['faces_by_tskin'].get(tskin, [])
                if not tris_list:
                    continue
                    
                color = colors[tskin % len(colors)]
                
                # Flat bright color with alpha based on slider
                shader.uniform_float("color", (*color[:3], alpha))

                verts = [data['verts_3d'][i] for tri in tris_list for i in tri]
                
                batch = batch_for_shader(shader, 'TRIS', {"pos": verts})
                batch.draw(shader)

    finally:
        # Restore original GPU states
        gpu.state.depth_test_set(original_depth_test)
        gpu.state.blend_set(original_blend)
        gpu.state.face_culling_set('NONE')

        # Free BMesh data
        for data in obj_data.values():
            data['bm'].free()

def draw_tskin_text(context):
    """Draws TSKIN values as text labels on face centers for selected mesh objects."""
    if context.scene.rsps_tskin_alpha <= 0.0:
        return

    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']

    if not selected_meshes:
        return

    font_id = 0
    blf.size(font_id, 12)
    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)  # White text for visibility

    region = context.region
    rv3d = context.region_data

    for obj in selected_meshes:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()

        tskin_layer = bm.loops.layers.color.get('RSTSKIN')
        if not tskin_layer:
            bm.free()
            continue

        for face in bm.faces:
            tskin_value = int(face.loops[0][tskin_layer][0] * 255)
            if tskin_value == 0:
                continue

            center = obj.matrix_world @ face.calc_center_median()

            # Project to 2D screen space
            coord_2d = location_3d_to_region_2d(region, rv3d, center)
            if coord_2d:
                blf.position(font_id, coord_2d.x + 5, coord_2d.y, 0)
                blf.draw(font_id, str(tskin_value))

        bm.free()

# --- Operators ---

class RSPS_OT_debug_materials_tskin(bpy.types.Operator):
    """Tests loading and parsing of material colors for TSKIN visualization."""
    bl_idname = "rsps.debug_materials_tskin"
    bl_label = "Test Material Loading (TSKIN)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        global PARSED_MATERIALS
        PARSED_MATERIALS = None
        colors = parse_material_colors()
        for i in range(min(10, len(colors))):
            color = colors[i]
            self.report({'INFO'}, f"Material {i}: R={color[0]:.3f} G={color[1]:.3f} B={color[2]:.3f}")
        self.report({'INFO'}, f"Loaded {len(colors)} material colors total")
        return {'FINISHED'}

class RSPS_OT_apply_tskin_by_number(bpy.types.Operator):
    """Applies TSKIN group data to selected faces."""
    bl_idname = "rsps.apply_tskin_by_number"
    bl_label = "Apply TSKIN by Number"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None and 
                context.active_object.type == 'MESH' and 
                context.mode == 'EDIT_MESH')

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        tskin_value = context.scene.rsps_tskin_to_apply
        
        if tskin_value < 0 or tskin_value > 255:
            self.report({'ERROR'}, "TSKIN must be between 0 and 255.")
            return {'CANCELLED'}
        
        colors = parse_material_colors()
        vis_color = colors[tskin_value % len(colors)]
        
        red_value = tskin_value / 255.0
        
        bm = bmesh.from_edit_mesh(mesh)
        
        tskin_layer = bm.loops.layers.color.get('RSTSKIN')
        if tskin_layer is None:
            tskin_layer = bm.loops.layers.color.new('RSTSKIN')
            self.report({'INFO'}, "Created 'RSTSKIN' vertex color layer for exporter.")

        vis_layer_name = f"RSTSKIN_{tskin_value}"
        vis_layer = bm.loops.layers.color.get(vis_layer_name)
        if vis_layer is None:
            vis_layer = bm.loops.layers.color.new(vis_layer_name)
            self.report({'INFO'}, f"Created visualization layer '{vis_layer_name}' with color for TSKIN {tskin_value}.")

        selected_faces = [f for f in bm.faces if f.select]
        if not selected_faces:
            self.report({'WARNING'}, "No faces are selected.")
            return {'CANCELLED'}

        tskin_data = (red_value, 0.0, 0.0, 1.0)
        vis_data = vis_color

        for face in selected_faces:
            for loop in face.loops:
                loop[tskin_layer] = tskin_data
                loop[vis_layer] = vis_data
        
        bmesh.update_edit_mesh(mesh)
        
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        
        self.report({'INFO'}, f"Applied TSKIN {tskin_value} to {len(selected_faces)} faces. Use '{vis_layer_name}' in Vertex Colors for display.")
        return {'FINISHED'}

# --- UI Panel ---

class VIEW3D_PT_rsps_tskins(bpy.types.Panel):
    bl_label = "TSKIN Painter"
    bl_idname = "VIEW3D_PT_rsps_tskins"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RSPS ADDON'
    bl_order = 3  # After Priorities (2), before Exporter (4 if adjusted)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        layout.box().label(text="TSKIN Painter", icon='BRUSH_DATA')
        obj = context.active_object
        
        if not obj or obj.type != 'MESH':
            layout.box().label(text="Select a mesh object first!", icon='ERROR')
            return

        apply_box = layout.box()
        apply_box.label(text="Apply TSKIN (Edit Mode)", icon='FONT_DATA')
        col = apply_box.column()
        col.enabled = (context.mode == 'EDIT_MESH')
        col.prop(scene, "rsps_tskin_to_apply")
        col.operator("rsps.apply_tskin_by_number", text="Apply to Selected Faces")
        if context.mode != 'EDIT_MESH':
            apply_box.label(text="Enter Edit Mode to use.", icon='INFO')
            
        vis_box = layout.box()
        vis_box.label(text="Visualization", icon='HIDE_OFF')
        vis_box.prop(scene, "rsps_tskin_alpha", text="TSKIN Intensity")
        vis_box.label(text="Controls overlay alpha (0=off) and shows labels on selected mesh objects (front-facing only, optimized)", icon='INFO')
        
        debug_box = layout.box()
        debug_box.label(text="Debug Tools", icon='CONSOLE')
        debug_box.operator("rsps.debug_materials_tskin", text="Test Material Loading")
        
        if obj and obj.type == 'MESH':
            if context.mode == 'EDIT_MESH':
                bm = bmesh.from_edit_mesh(obj.data)
                tskin_layer = bm.loops.layers.color.get('RSTSKIN')
                if tskin_layer:
                    debug_box.label(text="RSTSKIN layer found", icon='CHECKMARK')
                else:
                    debug_box.label(text="No RSTSKIN layer", icon='ERROR')

classes = (
    RSPS_OT_debug_materials_tskin,
    RSPS_OT_apply_tskin_by_number,
    VIEW3D_PT_rsps_tskins,
)
bpy.types.Scene.rsps_tskin_alpha = bpy.props.FloatProperty(
    name="TSKIN Alpha",
    description="Intensity of TSKIN visualization overlay",
    default=0.0,
    min=0.0,
    max=1.0,
    subtype='FACTOR'
)
bpy.types.Scene.rsps_tskin_to_apply = bpy.props.IntProperty(name="TSKIN Value", default=1, min=0, max=255)