# weighter.py
import bpy
import blf
import gpu
import re  # <-- ADDED: Import for regex matching
from bpy_extras.view3d_utils import location_3d_to_region_2d
# --- Global Configuration ---
# --- Helper & Core Functions ---
def force_viewport_redraw(self, context):
    """Forces all 3D views to redraw when the checkbox is toggled."""
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()
def draw_weights_callback(self, context):
    """Draws weight values on the 3D viewport."""
    ctx = bpy.context
    
    if not (hasattr(ctx.scene, 'show_weight_overlay') and ctx.scene.show_weight_overlay):
        return
        
    selected_objects = [obj for obj in ctx.selected_objects if obj.type == 'MESH']
    if not selected_objects:
        return
    
    font_id = 0
    blf.size(font_id, 16); blf.color(font_id, 0.2, 1.0, 0.8, 1.0); gpu.state.blend_set('ALPHA')
    
    region = ctx.region
    space_data = ctx.space_data
    
    for obj in selected_objects:
        if obj.hide_viewport or obj.hide_get() or not obj.visible_get():
            continue
        
        if not obj.vertex_groups:
            continue
        
        group_name = f"VSKIN{ctx.scene.vskin_layer}:"
        if group_name not in obj.vertex_groups:
            continue
        
        vg = obj.vertex_groups[group_name]
        vg_index = vg.index
        
        for vert in obj.data.vertices:
            if vert.hide:
                continue
                
            for group in vert.groups:
                if group.group == vg_index and group.weight > 0.001:
                    world_pos = obj.matrix_world @ vert.co
                    screen_pos = location_3d_to_region_2d(region, space_data.region_3d, world_pos)
                    
                    if screen_pos:
                        blf.position(font_id, screen_pos.x + 5, screen_pos.y + 5, 0)
                        blf.draw(font_id, f"{group.weight:.3f}")
                    break
def get_or_create_weight_group(obj, group_name):
    if group_name not in obj.vertex_groups:
        return obj.vertex_groups.new(name=group_name)
    return obj.vertex_groups[group_name]
def apply_weight_pro(context, obj, weight_value):
    was_in_edit = (obj.mode == 'EDIT')
    if was_in_edit: bpy.ops.object.mode_set(mode='OBJECT')
    selected_indices = [v.index for v in obj.data.vertices if v.select]
    if not selected_indices:
        if was_in_edit: bpy.ops.object.mode_set(mode='EDIT')
        return 0, "No vertices selected!"
    group_name = f"VSKIN{context.scene.vskin_layer}:"
    weight_group = get_or_create_weight_group(obj, group_name)
    weight_group.add(selected_indices, weight_value, 'REPLACE')
    obj.vertex_groups.active = weight_group
    if was_in_edit: bpy.ops.object.mode_set(mode='EDIT')
    return len(selected_indices), None
# --- Main Operators ---
class EPIC_OT_assign_weight(bpy.types.Operator):
    bl_idname = "epic.assign_weight"; bl_label = "Assign Preset Weight"; bl_options = {'REGISTER', 'UNDO'}
    part_name: bpy.props.StringProperty(default="Part")
    weight_value: bpy.props.FloatProperty(default=0.0)
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "⚠ Select a mesh object!"); return {'CANCELLED'}
        count, error = apply_weight_pro(context, obj, self.weight_value)
        if error:
            self.report({'WARNING'}, f"⚠ {error}"); return {'CANCELLED'}
        self.report({'INFO'}, f"✅ '{self.part_name}' weight ({self.weight_value:.3f}) applied to {count} vertices.")
        return {'FINISHED'}
class EPIC_OT_create_vskin(bpy.types.Operator):
    bl_idname = "epic.create_vskin"
    bl_label = "Create VSKIN Layer"
    bl_options = {'REGISTER', 'UNDO'}
    layer: bpy.props.IntProperty(default=1, min=1, max=3)
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh object first!")
            return {'CANCELLED'}
        group_name = f"VSKIN{self.layer}:"
        if group_name not in obj.vertex_groups:
            obj.vertex_groups.new(name=group_name)
            self.report({'INFO'}, f"Created {group_name}")
        else:
            self.report({'INFO'}, f"{group_name} already exists.")
        context.scene.vskin_layer = self.layer
        return {'FINISHED'}
class EPIC_OT_assign_custom(bpy.types.Operator):
    bl_idname = "epic.assign_custom"
    bl_label = "Assign Custom"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "⚠ Select a mesh object!"); return {'CANCELLED'}
        weight_value = context.scene.custom_weight
        count, error = apply_weight_pro(context, obj, weight_value)
        if error:
            self.report({'WARNING'}, f"⚠ {error}"); return {'CANCELLED'}
        self.report({'INFO'}, f"✅ Custom weight ({weight_value:.3f}) applied to {count} vertices.")
        return {'FINISHED'}
class EPIC_OT_create_and_apply_mirror(bpy.types.Operator):
    bl_idname = "epic.create_and_apply_mirror"; bl_label = "Finalise & Mirror Model"; bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "⚠ Select a mesh object first!"); return {'CANCELLED'}
        
        # Only process VSKIN1
        group_name = "VSKIN1:"
        if group_name not in obj.vertex_groups:
            self.report({'WARNING'}, f"⚠ {group_name} group not found! Create it first."); return {'CANCELLED'}
        
        self.report({'INFO'}, "Starting destructive mirror process...")
        original_mode = obj.mode
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        # Reset Location, Rotation, and Scale (Alt+G, Alt+R, Alt+S)
        bpy.ops.object.location_clear(clear_delta=False)
        bpy.ops.object.rotation_clear(clear_delta=False)
        bpy.ops.object.scale_clear(clear_delta=False)
        # Apply scale just in case (Ctrl+A -> Scale)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Select and delete the negative-X side of the mesh
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
        for v in obj.data.vertices:
            if v.co.x < -0.0001: v.select = True
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='VERT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Move the 3D Cursor to the World Origin (0,0,0)
        context.scene.cursor.location = (0.0, 0.0, 0.0)
        
        # Set the object's origin to the 3D Cursor
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        
        # Add and apply the mirror modifier
        mod = obj.modifiers.new(name="EpicFinalMirror", type='MIRROR')
        mod.use_axis[0] = True; mod.use_clip = True; mod.merge_threshold = 0.001; mod.use_mirror_vertex_groups = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        
        # Re-get the vertex group after modifier apply
        vg = obj.vertex_groups[group_name]
        vg_index = vg.index
        
        # Correct weights on the mirrored side (only for VSKIN1)
        weight_map = {0.25: 0.21, 0.26: 0.20, 0.23: 0.17, 0.22: 0.19, 0.28: 0.27, 0.40: 0.42, 0.43: 0.44,
                      0.35: 0.34, 0.36: 0.33, 0.37: 0.31, 0.38: 0.32, 0.47: 0.48, 0.46: 0.45}
        verts_to_correct = {}
        for v in obj.data.vertices:
            if v.co.x < -0.001:
                current_weight = 0.0
                for g in v.groups:
                    if g.group == vg_index: current_weight = g.weight; break
                if current_weight > 0.001:
                    rounded_weight = round(current_weight, 3)
                    new_weight = weight_map.get(rounded_weight, rounded_weight)
                    if new_weight != current_weight: verts_to_correct[v.index] = new_weight
        for index, weight in verts_to_correct.items(): vg.add([index], weight, 'REPLACE')
        
        if original_mode != 'OBJECT': bpy.ops.object.mode_set(mode=original_mode)
        self.report({'INFO'}, f"✅ Model finalised! Corrected {len(verts_to_correct)} weights.")
        return {'FINISHED'}
# --- All Body Part Buttons ---
class EPIC_OT_skull(EPIC_OT_assign_weight): bl_idname="epic.skull"; bl_label="Skull (0.01)"; part_name:bpy.props.StringProperty(default="Skull"); weight_value:bpy.props.FloatProperty(default=0.01)
class EPIC_OT_neck_upper(EPIC_OT_assign_weight): bl_idname="epic.neck_upper"; bl_label="N. Upper (0.03)"; part_name:bpy.props.StringProperty(default="Neck Upper"); weight_value:bpy.props.FloatProperty(default=0.03)
class EPIC_OT_neck_lower(EPIC_OT_assign_weight): bl_idname="epic.neck_lower"; bl_label="N. Lower (0.02)"; part_name:bpy.props.StringProperty(default="Neck Lower"); weight_value:bpy.props.FloatProperty(default=0.02)
class EPIC_OT_torso(EPIC_OT_assign_weight): bl_idname="epic.torso"; bl_label="Torso (0.08)"; part_name:bpy.props.StringProperty(default="Torso"); weight_value:bpy.props.FloatProperty(default=0.08)
class EPIC_OT_shoulder_joint(EPIC_OT_assign_weight): bl_idname="epic.shoulder_joint"; bl_label="S. Joint (0.25)"; part_name:bpy.props.StringProperty(default="Shoulder Joint"); weight_value:bpy.props.FloatProperty(default=0.25)
class EPIC_OT_shoulder_end(EPIC_OT_assign_weight): bl_idname="epic.shoulder_end"; bl_label="S. End (0.26)"; part_name:bpy.props.StringProperty(default="Shoulder End"); weight_value:bpy.props.FloatProperty(default=0.26)
class EPIC_OT_upper_arm(EPIC_OT_assign_weight): bl_idname="epic.upper_arm"; bl_label="Upper Arm (0.23)"; part_name:bpy.props.StringProperty(default="Upper Arm"); weight_value:bpy.props.FloatProperty(default=0.23)
class EPIC_OT_forearm(EPIC_OT_assign_weight): bl_idname="epic.forearm"; bl_label="Forearm (0.22)"; part_name:bpy.props.StringProperty(default="Forearm"); weight_value:bpy.props.FloatProperty(default=0.22)
class EPIC_OT_gloves(EPIC_OT_assign_weight): bl_idname="epic.gloves"; bl_label="Gloves (0.28)"; part_name:bpy.props.StringProperty(default="Gloves"); weight_value:bpy.props.FloatProperty(default=0.28)
class EPIC_OT_spine(EPIC_OT_assign_weight): bl_idname="epic.spine"; bl_label="Spine (0.29)"; part_name:bpy.props.StringProperty(default="Spine"); weight_value:bpy.props.FloatProperty(default=0.29)
class EPIC_OT_crotch(EPIC_OT_assign_weight): bl_idname="epic.crotch"; bl_label="Crotch (0.41)"; part_name:bpy.props.StringProperty(default="Crotch"); weight_value:bpy.props.FloatProperty(default=0.41)
class EPIC_OT_upper_leg_joint(EPIC_OT_assign_weight): bl_idname="epic.upper_leg_joint"; bl_label="UL. Joint (0.40)"; part_name:bpy.props.StringProperty(default="Upper Leg Joint"); weight_value:bpy.props.FloatProperty(default=0.40)
class EPIC_OT_upper_leg(EPIC_OT_assign_weight): bl_idname="epic.upper_leg"; bl_label="Upper Leg (0.43)"; part_name:bpy.props.StringProperty(default="Upper Leg"); weight_value:bpy.props.FloatProperty(default=0.43)
class EPIC_OT_knee_upper(EPIC_OT_assign_weight): bl_idname="epic.knee_upper"; bl_label="K. Upper (0.35)"; part_name:bpy.props.StringProperty(default="Knee Upper"); weight_value:bpy.props.FloatProperty(default=0.35)
class EPIC_OT_knee_middle(EPIC_OT_assign_weight): bl_idname="epic.knee_middle"; bl_label="K. Mid (0.36)"; part_name:bpy.props.StringProperty(default="Knee Middle"); weight_value:bpy.props.FloatProperty(default=0.36)
class EPIC_OT_knee_lower(EPIC_OT_assign_weight): bl_idname="epic.knee_lower"; bl_label="K. Lower (0.37)"; part_name:bpy.props.StringProperty(default="Knee Lower"); weight_value:bpy.props.FloatProperty(default=0.37)
class EPIC_OT_lower_leg(EPIC_OT_assign_weight): bl_idname="epic.lower_leg"; bl_label="Lower Leg (0.38)"; part_name:bpy.props.StringProperty(default="Lower Leg"); weight_value:bpy.props.FloatProperty(default=0.38)
class EPIC_OT_upper_boots(EPIC_OT_assign_weight): bl_idname="epic.upper_boots"; bl_label="B. Upper (0.38)"; part_name:bpy.props.StringProperty(default="Upper Boots"); weight_value:bpy.props.FloatProperty(default=0.38)
class EPIC_OT_mid_boots(EPIC_OT_assign_weight): bl_idname="epic.mid_boots"; bl_label="B. Mid (0.47)"; part_name:bpy.props.StringProperty(default="Mid Boots"); weight_value:bpy.props.FloatProperty(default=0.47)
class EPIC_OT_boots(EPIC_OT_assign_weight): bl_idname="epic.boots"; bl_label="Boots (0.46)"; part_name:bpy.props.StringProperty(default="Boots"); weight_value:bpy.props.FloatProperty(default=0.46)
class EPIC_OT_sword(EPIC_OT_assign_weight): bl_idname="epic.sword"; bl_label="Sword (0.50)"; part_name:bpy.props.StringProperty(default="Sword"); weight_value:bpy.props.FloatProperty(default=0.50)
class EPIC_OT_shield(EPIC_OT_assign_weight): bl_idname="epic.shield"; bl_label="Shield (0.28)"; part_name:bpy.props.StringProperty(default="Shield"); weight_value:bpy.props.FloatProperty(default=0.28)
class EPIC_OT_necklace(EPIC_OT_assign_weight): bl_idname="epic.necklace"; bl_label="Necklace (0.08)"; part_name:bpy.props.StringProperty(default="Necklace"); weight_value:bpy.props.FloatProperty(default=0.08)
# --- Management Tools ---
class EPIC_OT_clear_weights(bpy.types.Operator):
    bl_idname="epic.clear_weights"; bl_label="Clear All Weights"; bl_options={'REGISTER', 'UNDO'}
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh object first!"); return {'CANCELLED'}
        obj.vertex_groups.clear(); self.report({'INFO'}, "All vertex weights cleared!"); return {'FINISHED'}
class EPIC_OT_refresh_display(bpy.types.Operator):
    bl_idname = "epic.refresh_display"; bl_label = "Refresh Viewport"
    def execute(self, context):
        for area in context.screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()
        self.report({'INFO'}, "Viewport display refreshed."); return {'FINISHED'}
# --- UI Panel ---
class VIEW3D_PT_epic_weighter(bpy.types.Panel):
    bl_label = "Epic Model Weighter"; bl_idname = "VIEW3D_PT_epic_weighter"; bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'; bl_category = 'RSPS ADDON'
    def draw(self, context):
        layout = self.layout
        layout.box().label(text="🎯 EPIC MODEL WEIGHTER", icon='MODIFIER_DATA')
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            layout.box().label(text="❌ Select a mesh object first!", icon='ERROR')
            return
        
        tools_box = layout.box(); tools_box.label(text="🛠️ VSKIN Layers", icon='GROUP_VERTEX')
        row = tools_box.row(align=True)
        row.operator("epic.create_vskin", text="Create V1").layer=1
        row.operator("epic.create_vskin", text="Create V2").layer=2
        row.operator("epic.create_vskin", text="Create V3").layer=3
        if context.mode == 'EDIT_MESH':
            tools_box.prop(context.scene, "custom_weight", text="Weight Value")
            tools_box.operator("epic.assign_custom")
        
        if context.mode == 'EDIT_MESH':
            layout.label(text="Step 1: Weight your half-model (+X side)")
            head_box = layout.box(); head_box.label(text="👤 Head & Neck", icon='USER'); row = head_box.row(align=True)
            row.operator("epic.skull"); row.operator("epic.neck_upper"); row.operator("epic.neck_lower")
            torso_box = layout.box(); torso_box.label(text="💪 Torso & Arms", icon='POSE_HLT'); col = torso_box.column(align=True)
            col.operator("epic.torso"); row = col.row(align=True); row.operator("epic.shoulder_joint"); row.operator("epic.shoulder_end")
            row = col.row(align=True); row.operator("epic.upper_arm"); row.operator("epic.forearm")
            gloves_box = layout.box(); gloves_box.label(text="🧤 Gloves", icon='HAND'); gloves_box.operator("epic.gloves")
            pants_box = layout.box(); pants_box.label(text="👖 Legs", icon='MESH_MONKEY'); col = pants_box.column(align=True)
            row = col.row(align=True); row.operator("epic.spine"); row.operator("epic.crotch")
            row = col.row(align=True); row.operator("epic.upper_leg_joint"); row.operator("epic.upper_leg")
            row = col.row(align=True); row.operator("epic.knee_upper"); row.operator("epic.knee_middle"); row.operator("epic.knee_lower")
            col.operator("epic.lower_leg")
            boots_box = layout.box(); boots_box.label(text="👢 Boots", icon='MESH_CUBE'); row = boots_box.row(align=True)
            row.operator("epic.upper_boots"); row.operator("epic.mid_boots"); row.operator("epic.boots")
            accessories_box = layout.box(); accessories_box.label(text="Accessories", icon='MESH_UVSPHERE'); row = accessories_box.row(align=True)
            row.operator("epic.sword"); row.operator("epic.shield")
            row = accessories_box.row(align=True)
            row.operator("epic.necklace")
        
        layout.separator()
        finalise_box = layout.box(); finalise_box.label(text="Step 2: Create Full Model", icon='MOD_MIRROR')
        finalise_box.label(text="WARNING: This is a destructive action!", icon='ERROR')
        finalise_box.operator("epic.create_and_apply_mirror")
        layout.separator()
        tools_box = layout.box(); tools_box.label(text="🛠️ Tools & Display", icon='TOOL_SETTINGS')
        row = tools_box.row(align=True)
        row.operator("epic.refresh_display", icon='FILE_REFRESH'); row.operator("epic.clear_weights", icon='TRASH')
        tools_box.prop(context.scene, "show_weight_overlay", text="Show Weight Values", toggle=True)
# A tuple containing all classes from this file to be imported by __init__.py
classes = (
    EPIC_OT_assign_weight, EPIC_OT_skull, EPIC_OT_neck_upper, EPIC_OT_neck_lower, EPIC_OT_torso, EPIC_OT_shoulder_joint, 
    EPIC_OT_shoulder_end, EPIC_OT_upper_arm, EPIC_OT_forearm, EPIC_OT_gloves, EPIC_OT_spine, EPIC_OT_crotch, 
    EPIC_OT_upper_leg_joint, EPIC_OT_upper_leg, EPIC_OT_knee_upper, EPIC_OT_knee_middle, EPIC_OT_knee_lower, 
    EPIC_OT_lower_leg, EPIC_OT_upper_boots, EPIC_OT_mid_boots, EPIC_OT_boots, EPIC_OT_create_and_apply_mirror, 
    EPIC_OT_clear_weights, EPIC_OT_refresh_display, EPIC_OT_create_vskin, EPIC_OT_assign_custom, 
    EPIC_OT_sword, EPIC_OT_shield, EPIC_OT_necklace, VIEW3D_PT_epic_weighter,
)
bpy.types.Scene.vskin_layer = bpy.props.IntProperty(name="VSKIN Layer", default=1, min=1, max=3, update=force_viewport_redraw)
bpy.types.Scene.custom_weight = bpy.props.FloatProperty(name="Custom Weight", default=0.0, min=0.0, max=1.0)
bpy.types.Scene.show_weight_overlay = bpy.props.BoolProperty(default=False, update=force_viewport_redraw)