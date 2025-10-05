# aether_materials.py
# Aether Materials - Color Tinting and Alpha Transparency System
# Integrated into RSPS ADDON

import bpy
import random
from colorsys import rgb_to_hsv, hsv_to_rgb
from bpy_extras.io_utils import ImportHelper
from collections import defaultdict

# ===============================================================
# TEXTURE SELECTION & MATERIAL CREATION
# ===============================================================

class AETHER_OT_SelectTexture(bpy.types.Operator, ImportHelper):
    """Select texture to create materials from UV colors"""
    bl_idname = "aether.select_texture"
    bl_label = "Select Texture"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: bpy.props.StringProperty(default="*.png;*.jpg;*.tga;*.dds;*.jpeg", options={'HIDDEN'})

    def execute(self, context):
        texture_path = self.filepath
        result = self.create_materials_from_texture(context, texture_path)
        if result:
            self.report({'INFO'}, f"Created materials from texture")
        return {'FINISHED'}

    def create_materials_from_texture(self, context, texture_path):
        """Creates materials from texture based on UV coordinates"""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Selected object is not a mesh.")
            return False

        uv_map = obj.data.uv_layers.active
        if not uv_map:
            self.report({'ERROR'}, "No active UV map found.")
            return False

        texture_image = bpy.data.images.load(texture_path, check_existing=True)
        materials_dict = {}

        def sample_color(uv_coords):
            width, height = texture_image.size
            pixel_x = int(uv_coords[0] * width)
            pixel_y = int(uv_coords[1] * height)

            if 0 <= pixel_x < width and 0 <= pixel_y < height:
                pixel_index = (pixel_y * width + pixel_x) * 4
                return tuple(texture_image.pixels[pixel_index:pixel_index + 4])
            return None

        for face in obj.data.polygons:
            total_uv = [0, 0]
            for loop_index in face.loop_indices:
                uv_coords = uv_map.data[loop_index].uv
                total_uv[0] += uv_coords[0]
                total_uv[1] += uv_coords[1]

            avg_uv = [coord / len(face.loop_indices) for coord in total_uv]
            color = sample_color(avg_uv)

            if color is not None:
                if color not in materials_dict:
                    material_name = f"Aether_Mat_{len(materials_dict)}"
                    material = bpy.data.materials.new(name=material_name)
                    material.use_nodes = True
                    bsdf = material.node_tree.nodes["Principled BSDF"]
                    bsdf.inputs["Base Color"].default_value = color
                    bsdf.inputs["Roughness"].default_value = 1.0
                    materials_dict[color] = material

                mat = materials_dict[color]
                if obj.data.materials.find(mat.name) == -1:
                    obj.data.materials.append(mat)
                face.material_index = obj.data.materials.find(mat.name)

        self.store_original_colors(obj)
        return True

    def store_original_colors(self, obj):
        """Store current colors as original"""
        obj["original_colors"] = {}
        for mat in obj.data.materials:
            if mat and mat.use_nodes:
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    current_color = bsdf.inputs['Base Color'].default_value[:3]
                    obj["original_colors"][mat.name] = current_color

# ===============================================================
# COLOR ADJUSTMENT FUNCTIONS
# ===============================================================

def update_material_colors(self, context):
    """Update material colors based on RGB/HSV sliders for all selected objects"""
    selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
    
    if not selected_objects:
        return
    
    # Get RGB properties from scene
    rgb_props = context.scene.aether_rgb_props
    
    for obj in selected_objects:
        if "original_colors" not in obj:
            store_original_colors(obj)
        
        for mat in obj.data.materials:
            if mat and mat.use_nodes:
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    base_mat_name = mat.name.replace("_Transparent", "")
                    original_color = obj["original_colors"].get(mat.name, 
                                                                 obj["original_colors"].get(base_mat_name, (1, 1, 1)))
                    
                    hsv_color = rgb_to_hsv(*original_color)
                    new_h = (hsv_color[0] + rgb_props.hue_value) % 1
                    
                    new_s = hsv_color[1] * rgb_props.saturation_value
                    # Only boost saturation for whites/grays if properties are NOT at default values
                    if hsv_color[1] < 0.1 and (rgb_props.hue_value != 0.0 or rgb_props.saturation_value != 1.0 or rgb_props.value_value != 1.0):
                        new_s = 0.8 * rgb_props.saturation_value
                    
                    new_v = hsv_color[2] * rgb_props.value_value
                    tinted_rgb = hsv_to_rgb(new_h, new_s, new_v)

                    final_color = (
                        tinted_rgb[0] * rgb_props.r_value,
                        tinted_rgb[1] * rgb_props.g_value,
                        tinted_rgb[2] * rgb_props.b_value,
                        1
                    )
                    bsdf.inputs['Base Color'].default_value = final_color

def update_alpha_transparency(self, context):
    """Update alpha transparency for materials on selected faces"""
    selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
    
    if not selected_objects:
        return
    
    # Get RGB properties from scene
    rgb_props = context.scene.aether_rgb_props
    alpha = rgb_props.alpha_value / 100.0
    
    for obj in selected_objects:
        # Only update if in Edit Mode to respect face selection
        if obj.mode == 'EDIT':
            import bmesh
            bm = bmesh.from_edit_mesh(obj.data)
            selected_faces = [f for f in bm.faces if f.select]
            
            if not selected_faces:
                continue
            
            # Get material indices of selected faces only
            selected_mat_indices = set(f.material_index for f in selected_faces)
            
            # Update alpha only for materials used by selected faces
            for mat_idx in selected_mat_indices:
                if mat_idx < len(obj.data.materials):
                    mat = obj.data.materials[mat_idx]
                    if mat and mat.use_nodes and mat.blend_method == 'BLEND':
                        bsdf = mat.node_tree.nodes.get("Principled BSDF")
                        if bsdf:
                            bsdf.inputs['Alpha'].default_value = alpha
        else:
            # In Object Mode, update all materials with alpha enabled
            for mat in obj.data.materials:
                if mat and mat.use_nodes and mat.blend_method == 'BLEND':
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        bsdf.inputs['Alpha'].default_value = alpha

def store_original_colors(obj):
    """Store the current colors as original"""
    obj["original_colors"] = {}
    for mat in obj.data.materials:
        if mat and mat.use_nodes:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                current_color = bsdf.inputs['Base Color'].default_value[:3]
                obj["original_colors"][mat.name] = current_color

def reset_rgb_properties(rgb_props):
    """Reset RGB properties to defaults"""
    rgb_props.r_value = 1.0
    rgb_props.g_value = 1.0
    rgb_props.b_value = 1.0
    rgb_props.hue_value = 0.0
    rgb_props.saturation_value = 1.0
    # THIS IS THE CORRECTED LINE
    rgb_props.value_value = 1.0 
    rgb_props.alpha_value = 100.0

# ===============================================================
# PRESET DEFINITIONS - CURATED COLLECTION
# ===============================================================

PRESETS = {
    # Red Family
    "Crimson": {"r": 0.86, "g": 0.08, "b": 0.24, "h": 0.98, "s": 0.91, "v": 0.6},
    "Ruby": {"r": 0.88, "g": 0.07, "b": 0.37, "h": 0.95, "s": 0.92, "v": 0.8},
    "Wine": {"r": 0.45, "g": 0.09, "b": 0.09, "h": 0.0, "s": 0.8, "v": 0.35},
    
    # Orange Family
    "Tangerine": {"r": 0.95, "g": 0.52, "b": 0.0, "h": 0.09, "s": 1.0, "v": 1.0},
    "Copper": {"r": 0.72, "g": 0.45, "b": 0.2, "h": 0.08, "s": 0.72, "v": 0.7},
    
    # Yellow/Gold Family
    "Gold": {"r": 1.0, "g": 0.84, "b": 0.0, "h": 0.14, "s": 1.0, "v": 1.3},
    "Honey": {"r": 0.9, "g": 0.7, "b": 0.2, "h": 0.14, "s": 0.78, "v": 0.9},
    
    # Green Family
    "Emerald": {"r": 0.08, "g": 0.78, "b": 0.38, "h": 0.35, "s": 0.9, "v": 0.78},
    "Jade": {"r": 0.0, "g": 0.66, "b": 0.42, "h": 0.36, "s": 1.0, "v": 0.7},
    "Lime": {"r": 0.75, "g": 1.0, "b": 0.0, "h": 0.19, "s": 1.0, "v": 1.2},
    "Forest": {"r": 0.13, "g": 0.55, "b": 0.13, "h": 0.33, "s": 0.76, "v": 0.5},
    
    # Cyan/Teal Family
    "Cyan": {"r": 0.0, "g": 1.0, "b": 1.0, "h": 0.5, "s": 1.0, "v": 1.3},
    "Turquoise": {"r": 0.19, "g": 0.84, "b": 0.78, "h": 0.48, "s": 0.77, "v": 0.95},
    "Teal": {"r": 0.0, "g": 0.5, "b": 0.5, "h": 0.5, "s": 1.0, "v": 0.55},
    
    # Blue Family
    "Sapphire": {"r": 0.06, "g": 0.32, "b": 0.73, "h": 0.6, "s": 0.92, "v": 0.75},
    "Cobalt": {"r": 0.0, "g": 0.28, "b": 0.67, "h": 0.61, "s": 1.0, "v": 0.7},
    "Sky": {"r": 0.53, "g": 0.81, "b": 0.92, "h": 0.57, "s": 0.43, "v": 1.0},
    "Navy": {"r": 0.0, "g": 0.0, "b": 0.5, "h": 0.67, "s": 1.0, "v": 0.4},
    
    # Purple Family
    "Amethyst": {"r": 0.6, "g": 0.4, "b": 0.8, "h": 0.75, "s": 0.5, "v": 0.85},
    "Violet": {"r": 0.93, "g": 0.51, "b": 0.93, "h": 0.83, "s": 0.45, "v": 1.0},
    "Indigo": {"r": 0.29, "g": 0.0, "b": 0.51, "h": 0.76, "s": 1.0, "v": 0.5},
    
    # Pink/Magenta Family
    "Magenta": {"r": 1.0, "g": 0.0, "b": 0.75, "h": 0.88, "s": 1.0, "v": 1.1},
    "Hot Pink": {"r": 1.0, "g": 0.41, "b": 0.71, "h": 0.92, "s": 0.59, "v": 1.0},
    "Rose": {"r": 1.0, "g": 0.0, "b": 0.5, "h": 0.92, "s": 1.0, "v": 0.9},
    
    # Metallic Family
    "Silver": {"r": 0.75, "g": 0.75, "b": 0.75, "h": 0.0, "s": 0.0, "v": 1.5},
    "Platinum": {"r": 0.9, "g": 0.89, "b": 0.89, "h": 0.0, "s": 0.01, "v": 1.8},
    "Bronze": {"r": 0.8, "g": 0.5, "b": 0.2, "h": 0.08, "s": 0.75, "v": 0.75},
    
    # Dark/Shadow
    "Obsidian": {"r": 0.05, "g": 0.05, "b": 0.05, "h": 0.0, "s": 0.0, "v": 0.1},
    "Shadow": {"r": 0.5, "g": 0.15, "b": 0.7, "h": 0.76, "s": 0.79, "v": 0.5},
    
    # Mystical/Fantasy
    "Arcane": {"r": 0.4, "g": 0.15, "b": 0.8, "h": 0.73, "s": 0.81, "v": 0.85},
    "Celestial": {"r": 0.53, "g": 0.81, "b": 0.98, "h": 0.57, "s": 0.46, "v": 1.2},
    "Ethereal": {"r": 0.8, "g": 0.7, "b": 1.0, "h": 0.73, "s": 0.3, "v": 1.3},
}

# ===============================================================
# PRESET OPERATORS
# ===============================================================

class AETHER_OT_ApplyPreset(bpy.types.Operator):
    """Apply a color preset to RGB properties"""
    bl_idname = "aether.apply_preset"
    bl_label = "Apply Preset"
    bl_options = {'REGISTER', 'UNDO'}
    
    preset_name: bpy.props.StringProperty()

    def execute(self, context):
        # Use scene-level properties
        rgb_props = context.scene.aether_rgb_props
        
        if self.preset_name in PRESETS:
            preset = PRESETS[self.preset_name]
            rgb_props.r_value = preset["r"]
            rgb_props.g_value = preset["g"]
            rgb_props.b_value = preset["b"]
            rgb_props.hue_value = preset["h"]
            rgb_props.saturation_value = preset["s"]
            rgb_props.value_value = preset["v"]
            # Trigger update
            update_material_colors(None, context)
        
        self.report({'INFO'}, f"Applied preset: {self.preset_name}")
        return {'FINISHED'}

# ===============================================================
# PROPERTY GROUP
# ===============================================================

class RGBProperties(bpy.types.PropertyGroup):
    """RGB and HSV color control properties"""
    r_value: bpy.props.FloatProperty(
        name="R", description="Red Tint", 
        default=1.0,
        update=update_material_colors)
    g_value: bpy.props.FloatProperty(
        name="G", description="Green Tint", 
        default=1.0,
        update=update_material_colors)
    b_value: bpy.props.FloatProperty(
        name="B", description="Blue Tint", 
        default=1.0,
        update=update_material_colors)
    
    hue_value: bpy.props.FloatProperty(
        name="Hue", description="Hue Adjustment", 
        default=0.0,
        update=update_material_colors)
    saturation_value: bpy.props.FloatProperty(
        name="Saturation", description="Saturation Adjustment", 
        default=1.0,
        update=update_material_colors)
    value_value: bpy.props.FloatProperty(
        name="Value", description="Value Adjustment", 
        default=1.0,
        update=update_material_colors)
    
    alpha_value: bpy.props.FloatProperty(
        name="Alpha (%)", description="Transparency level", 
        default=100.0,
        update=update_alpha_transparency)

# ===============================================================
# OPERATORS
# ===============================================================

class AETHER_OT_ResetMaterials(bpy.types.Operator):
    """Reset all materials to their original colors on all selected objects"""
    bl_idname = "aether.reset_materials"
    bl_label = "Reset to Original Colors"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        reset_count = 0
        
        for obj in selected_objects:
            if "original_colors" in obj:
                for mat in obj.data.materials:
                    if mat and mat.use_nodes:
                        bsdf = mat.node_tree.nodes.get("Principled BSDF")
                        if bsdf:
                            base_mat_name = mat.name.replace("_Transparent", "")
                            original_color = obj["original_colors"].get(mat.name, 
                                                                         obj["original_colors"].get(base_mat_name, (1, 1, 1)))
                            bsdf.inputs['Base Color'].default_value = (*original_color, 1)
                            if "_Transparent" in mat.name or mat.blend_method == 'BLEND':
                                bsdf.inputs['Alpha'].default_value = 1.0
                
                reset_count += 1
        
        # Reset scene-level RGB properties
        reset_rgb_properties(context.scene.aether_rgb_props)
        
        if reset_count > 0:
            self.report({'INFO'}, f"Reset {reset_count} object(s) to original colors")
        else:
            self.report({'WARNING'}, "No objects with stored colors found")
        return {'FINISHED'}

class AETHER_OT_RandomizeColors(bpy.types.Operator):
    """Randomize colors with same harmonious theme for all selected objects"""
    bl_idname = "aether.randomize_colors"
    bl_label = "Randomize Colors (Same Theme)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            self.report({'WARNING'}, "No mesh objects selected")
            return {'CANCELLED'}

        # Pick ONE random base hue for ALL selected objects
        base_hue = random.random()  # Random hue 0.0 to 1.0

        for obj in selected_objects:
            if "original_colors" not in obj:
                store_original_colors(obj)
            
            for mat in obj.data.materials:
                if mat and mat.use_nodes:
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        # All objects use same base_hue with slight variations
                        h_val = (base_hue + random.uniform(-0.1, 0.1)) % 1.0
                        # Random saturation and value for variety
                        s_val = random.uniform(0.6, 0.95)
                        v_val = random.uniform(0.5, 0.9)
                        
                        rand_rgb = hsv_to_rgb(h_val, s_val, v_val)
                        bsdf.inputs['Base Color'].default_value = (*rand_rgb, 1)

        self.report({'INFO'}, f"Applied same random theme to {len(selected_objects)} object(s)")
        return {'FINISHED'}


class AETHER_OT_ApplyOriginalColors(bpy.types.Operator):
    """Store current colors as new original colors for all selected objects"""
    bl_idname = "aether.apply_original_colors"
    bl_label = "Apply Original Colors"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            self.report({'WARNING'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        for obj in selected_objects:
            store_original_colors(obj)
        
        self.report({'INFO'}, f"Applied current colors as original for {len(selected_objects)} object(s)")
        return {'FINISHED'}

class AETHER_OT_EnableAlpha(bpy.types.Operator):
    """Enable transparency on materials of selected faces"""
    bl_idname = "aether.enable_alpha"
    bl_label = "Enable Alpha on Selected Faces"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh object.")
            return {'CANCELLED'}
        
        # Ensure we're in Edit Mode
        original_mode = obj.mode
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Switch to Object Mode to read face selection
        bpy.ops.object.mode_set(mode='OBJECT')
        
        selected_faces = [f for f in obj.data.polygons if f.select]
        if not selected_faces:
            self.report({'WARNING'}, "No faces selected.")
            bpy.ops.object.mode_set(mode=original_mode)
            return {'CANCELLED'}
        
        # Get unique material indices from selected faces
        selected_mat_indices = set(f.material_index for f in selected_faces)
        
        # Enable alpha on those materials
        materials_affected = 0
        for mat_idx in selected_mat_indices:
            if mat_idx < len(obj.data.materials):
                mat = obj.data.materials[mat_idx]
                if mat and mat.use_nodes:
                    # Enable alpha blending
                    mat.blend_method = 'BLEND'
                    
                    # Set shadow method if the attribute exists (older Blender versions)
                    if hasattr(mat, 'shadow_method'):
                        mat.shadow_method = 'CLIP'
                    
                    # Set initial alpha value
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        bsdf.inputs['Alpha'].default_value = 0.5
                        materials_affected += 1
        
        # Set initial alpha value in scene properties
        context.scene.aether_rgb_props.alpha_value = 50.0
        
        # Return to original mode
        bpy.ops.object.mode_set(mode=original_mode)
        
        self.report({'INFO'}, f"Enabled alpha on {materials_affected} material(s) for {len(selected_faces)} selected faces")
        return {'FINISHED'}

# ===============================================================
# UI PANELS (Integrated into RSPS ADDON)
# ===============================================================

class AETHER_PT_ColorTint(bpy.types.Panel):
    """Aether Color Tint Panel - Integrated into Texture Tool"""
    bl_label = "Aether Color Tint"
    bl_idname = "AETHER_PT_color_tint"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RSPS ADDON'
    bl_parent_id = "OBJECT_PT_rs_pmn_texturing"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        selected_mesh_count = len([o for o in context.selected_objects if o.type == 'MESH'])

        rgb_props = context.scene.aether_rgb_props

        if obj and obj.type == 'MESH':
            if selected_mesh_count > 1:
                info_box = layout.box()
                info_box.label(text=f"Selected: {selected_mesh_count} objects", icon='OBJECT_DATA')

            box = layout.box()
            box.label(text="UV to Materials:", icon='MATERIAL')
            box.operator("aether.select_texture")

            presets_box = layout.box()
            presets_box.label(text="Presets:", icon='COLOR')
            row = presets_box.row(align=True)
            for i, (name, _) in enumerate(PRESETS.items()):
                if i % 5 == 0 and i > 0:
                    row = presets_box.row(align=True)
                op = row.operator("aether.apply_preset", text=name, icon='COLOR')
                op.preset_name = name

            box = layout.box()
            box.label(text="Color Controls:", icon='COLOR')
            if selected_mesh_count > 1:
                box.label(text="Affects all selected objects", icon='INFO')
            box.prop(rgb_props, "r_value")
            box.prop(rgb_props, "g_value")
            box.prop(rgb_props, "b_value")
            box.prop(rgb_props, "hue_value")
            box.prop(rgb_props, "saturation_value")
            box.prop(rgb_props, "value_value")
            
            box.separator()
            box.operator("aether.apply_original_colors", text="Apply Original Colors")
            box.operator("aether.reset_materials", text="Reset to Original Colors")
            box.operator("aether.randomize_colors", text="Randomize (Varied)")

            box = layout.box()
            box.label(text="Alpha Transparency:", icon='SHADING_RENDERED')
            
            if context.mode == 'EDIT_MESH':
                box.label(text="1. Select faces", icon='EDITMODE_HLT')
                box.label(text="2. Enable alpha on their materials:")
                box.operator("aether.enable_alpha")
                
                import bmesh
                bm = bmesh.from_edit_mesh(obj.data)
                selected_faces = [f for f in bm.faces if f.select]
                selected_mat_indices = set(f.material_index for f in selected_faces) if selected_faces else set()
                
                has_alpha_enabled = False
                for mat_idx in selected_mat_indices:
                    if mat_idx < len(obj.data.materials):
                        mat = obj.data.materials[mat_idx]
                        if mat and mat.blend_method == 'BLEND':
                            has_alpha_enabled = True
                            break
                
                if has_alpha_enabled:
                    box.separator()
                    box.label(text="Alpha Control (Selected Materials):")
                    if selected_mesh_count > 1:
                        box.label(text="Affects selected faces on all objects", icon='INFO')
                    box.prop(rgb_props, "alpha_value")
                else:
                    box.label(text="Select faces with alpha to adjust", icon='INFO')
            else:
                box.label(text="Enter Edit Mode to enable alpha", icon='INFO')
                
                has_alpha = any(mat.blend_method == 'BLEND' for mat in obj.data.materials if mat)
                if has_alpha:
                    box.separator()
                    box.label(text="Alpha Control (All Alpha Materials):")
                    if selected_mesh_count > 1:
                        box.label(text="Affects all selected objects", icon='INFO')
                    box.prop(rgb_props, "alpha_value")

# ===============================================================
# REGISTRATION
# ===============================================================

classes = (
    RGBProperties,
    AETHER_OT_SelectTexture,
    AETHER_OT_ResetMaterials,
    AETHER_OT_RandomizeColors,
    AETHER_OT_ApplyOriginalColors,
    AETHER_OT_EnableAlpha,
    AETHER_OT_ApplyPreset,
    AETHER_PT_ColorTint,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register scene-level properties
    bpy.types.Scene.aether_rgb_props = bpy.props.PointerProperty(type=RGBProperties)

def unregister():
    # Unregister scene-level properties
    del bpy.types.Scene.aether_rgb_props
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()