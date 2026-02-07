# aether_materials.py
# Aether Materials - Professional Color Engine for OSRS Models
# Optimized for 1000+ Principled BSDF materials
import bpy
import random
from colorsys import rgb_to_hsv, hsv_to_rgb
import bmesh
# ===============================================================
# CORE UTILITIES
# ===============================================================
def store_original_colors(obj):
    """Saves the current base colors so we can offset from them."""
    if "original_colors" not in obj:
        obj["original_colors"] = {}
    for mat in obj.data.materials:
        if mat and mat.use_nodes:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                color = bsdf.inputs['Base Color'].default_value
                obj["original_colors"][mat.name] = list(color[:3])

def duplicate_shared_materials(obj):
    """Duplicate materials that are shared between selected and non-selected faces in Edit Mode."""
    if obj.mode != 'EDIT':
        return
    bm = bmesh.from_edit_mesh(obj.data)
    selected_faces = [f for f in bm.faces if f.select]
    if not selected_faces:
        bmesh.update_edit_mesh(obj.data)
        return
    for mat_idx in set(f.material_index for f in selected_faces):
        non_selected = any(not f.select and f.material_index == mat_idx for f in bm.faces)
        if non_selected:
            old_mat = obj.data.materials[mat_idx]
            if old_mat:
                new_mat = old_mat.copy()
                new_mat.name = old_mat.name + "_unique"
                obj.data.materials.append(new_mat)
                new_idx = len(obj.data.materials) - 1
                for f in selected_faces:
                    if f.material_index == mat_idx:
                        f.material_index = new_idx
                if "original_colors" in obj:
                    orig = obj["original_colors"].get(old_mat.name, [0.8, 0.8, 0.8])
                    obj["original_colors"][new_mat.name] = orig[:]
    bmesh.update_edit_mesh(obj.data)

def refresh_materials(context):
    """Forces all selected objects to re-calculate their colors."""
    props = context.scene.aether_rgb_props
    selected_objs = [o for o in context.selected_objects if o.type == 'MESH']
    alpha = props.alpha_value / 100.0
    for obj in selected_objs:
        if "original_colors" not in obj or not obj["original_colors"]:
            store_original_colors(obj)
        duplicate_shared_materials(obj)
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data)
            selected_mat_indices = {f.material_index for f in bm.faces if f.select}
            mats_to_process = [(i, obj.data.materials[i]) for i in selected_mat_indices
                              if i < len(obj.data.materials) and obj.data.materials[i]]
        else:
            mats_to_process = [(i, mat) for i, mat in enumerate(obj.data.materials) if mat]
        for mat_index, mat in mats_to_process:
            if not mat or not mat.use_nodes:
                continue
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if not bsdf:
                continue
            orig = obj["original_colors"].get(mat.name, [0.8, 0.8, 0.8])
            r, g, b = orig[0], orig[1], orig[2]
            r *= props.r_value
            g *= props.g_value
            b *= props.b_value
            max_val = max(r, g, b)
            if max_val > 0.001:
                r_norm = r / max_val
                g_norm = g / max_val
                b_norm = b / max_val
                h, s, v = rgb_to_hsv(r_norm, g_norm, b_norm)
                h = (h + props.hue_value) % 1.0
                s = max(0.0, min(1.0, s * props.saturation_value))
                r_norm, g_norm, b_norm = hsv_to_rgb(h, s, v)
                r = r_norm * max_val
                g = g_norm * max_val
                b = b_norm * max_val
            r *= props.value_value
            g *= props.value_value
            b *= props.value_value
            r *= props.brightness_value
            g *= props.brightness_value
            b *= props.brightness_value
            if props.contrast_value != 1.0:
                r = 0.5 + (r - 0.5) * props.contrast_value
                g = 0.5 + (g - 0.5) * props.contrast_value
                b = 0.5 + (b - 0.5) * props.contrast_value
            if props.warmth_value != 0.0:
                shift = props.warmth_value * 0.3
                r += shift
                g += shift * 0.5
                b -= shift
            if props.tint_value != 0.0:
                shift = props.tint_value * 0.3
                g += shift
                r -= shift * 0.3
                b -= shift * 0.3
            if props.vibrance_value != 0.0:
                max_val = max(r, g, b)
                if max_val > 0.001:
                    r_norm = r / max_val
                    g_norm = g / max_val
                    b_norm = b / max_val
                    h_tmp, s_tmp, v_tmp = rgb_to_hsv(r_norm, g_norm, b_norm)
                    if props.vibrance_value > 0:
                        sat_boost = props.vibrance_value * (1.0 - s_tmp) * 3.0
                        s_tmp = max(0.0, min(1.0, s_tmp + sat_boost))
                    else:
                        s_tmp = max(0.0, s_tmp + (props.vibrance_value * 2.0))
                    r_norm, g_norm, b_norm = hsv_to_rgb(h_tmp, s_tmp, v_tmp)
                    r = r_norm * max_val
                    g = g_norm * max_val
                    b = b_norm * max_val
            if props.color_rotation_value != 0.0:
                r_orig, g_orig, b_orig = r, g, b
                rot = props.color_rotation_value
                if rot > 0:
                    mix = rot
                    r = r_orig * (1 - mix) + g_orig * mix
                    g = g_orig * (1 - mix) + b_orig * mix
                    b = b_orig * (1 - mix) + r_orig * mix
                else:
                    mix = abs(rot)
                    r = r_orig * (1 - mix) + b_orig * mix
                    g = g_orig * (1 - mix) + r_orig * mix
                    b = b_orig * (1 - mix) + g_orig * mix
            # NEW: Shadows control (-1 to +1)
            shadows = props.shadows_value
            if shadows > 0.0:
                crush = shadows
                r *= (1.0 - crush)
                g *= (1.0 - crush)
                b *= (1.0 - crush)
            elif shadows < 0.0:
                lift = -shadows
                r += lift * (1.0 - r)
                g += lift * (1.0 - g)
                b += lift * (1.0 - b)
            # FINAL CLAMP (allows pure black)
            r = max(0.0, min(3.0, r))
            g = max(0.0, min(3.0, g))
            b = max(0.0, min(3.0, b))
            bsdf.inputs['Base Color'].default_value = (r, g, b, 1.0)
            bsdf.inputs['Alpha'].default_value = alpha
            mat.blend_method = 'BLEND' if alpha < 1.0 else 'OPAQUE'
# ===============================================================
# OPERATORS
# ===============================================================
class AETHER_OT_OptimizeShading(bpy.types.Operator):
    bl_idname = "aether.optimize_shading"
    bl_label = "Optimize OSRS Shading"
    bl_description = "Apply flat shading and remove specular/metallic effects"
    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.shade_flat()
            for mat in obj.data.materials:
                if mat and mat.use_nodes:
                    principled = mat.node_tree.nodes.get("Principled BSDF")
                    if principled:
                        principled.inputs['Roughness'].default_value = 1.0
                        principled.inputs['Metallic'].default_value = 0.0
                        if 'Specular IOR Level' in principled.inputs:
                            principled.inputs['Specular IOR Level'].default_value = 0.0
                        elif 'Specular' in principled.inputs:
                            principled.inputs['Specular'].default_value = 0.0
                        if 'Coat Weight' in principled.inputs:
                            principled.inputs['Coat Weight'].default_value = 0.0
                        if 'Sheen Weight' in principled.inputs:
                            principled.inputs['Sheen Weight'].default_value = 0.0
                        if 'Emission Strength' in principled.inputs:
                            principled.inputs['Emission Strength'].default_value = 0.0
                        count += 1
        self.report({'INFO'}, f"Optimized {count} materials")
        return {'FINISHED'}

class AETHER_OT_ApplyPreset(bpy.types.Operator):
    bl_idname = "aether.apply_preset"
    bl_label = "Apply Preset"
    preset_name: bpy.props.StringProperty()
    def execute(self, context):
        props = context.scene.aether_rgb_props
        p = PRESETS.get(self.preset_name)
        if p:
            props.r_value = p["r"]
            props.g_value = p["g"]
            props.b_value = p["b"]
            props.hue_value = p["h"]
            props.saturation_value = p["s"]
            props.value_value = p["v"]
            props.brightness_value = p.get("brightness", 1.0)
            props.contrast_value = p.get("contrast", 1.0)
            props.warmth_value = p.get("warmth", 0.0)
            props.tint_value = p.get("tint", 0.0)
            props.vibrance_value = p.get("vibrance", 0.0)
            props.color_rotation_value = p.get("rotation", 0.0)
            props.shadows_value = p.get("shadows", 0.0)
            refresh_materials(context)
            self.report({'INFO'}, f"Applied {self.preset_name}")
        return {'FINISHED'}

class AETHER_OT_ResetMaterials(bpy.types.Operator):
    bl_idname = "aether.reset_materials"
    bl_label = "Reset"
    bl_description = "Reset all controls and restore original colors"
    def execute(self, context):
        props = context.scene.aether_rgb_props
        props.r_value = 1.0
        props.g_value = 1.0
        props.b_value = 1.0
        props.hue_value = 0.0
        props.saturation_value = 1.0
        props.value_value = 1.0
        props.brightness_value = 1.0
        props.contrast_value = 1.0
        props.warmth_value = 0.0
        props.tint_value = 0.0
        props.vibrance_value = 0.0
        props.color_rotation_value = 0.0
        props.shadows_value = 0.0
        props.alpha_value = 100.0
        for obj in context.selected_objects:
            if obj.type != 'MESH' or "original_colors" not in obj:
                continue
            if obj.mode == 'EDIT':
                bm = bmesh.from_edit_mesh(obj.data)
                selected_mat_indices = {f.material_index for f in bm.faces if f.select}
                mats_to_reset = [(i, obj.data.materials[i]) for i in selected_mat_indices
                                if i < len(obj.data.materials) and obj.data.materials[i]]
            else:
                mats_to_reset = [(i, mat) for i, mat in enumerate(obj.data.materials) if mat]
            for mat_index, mat in mats_to_reset:
                if mat and mat.use_nodes and mat.name in obj["original_colors"]:
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        orig = obj["original_colors"][mat.name]
                        bsdf.inputs['Base Color'].default_value = (orig[0], orig[1], orig[2], 1.0)
                        bsdf.inputs['Alpha'].default_value = 1.0
                        mat.blend_method = 'OPAQUE'
        self.report({'INFO'}, "Reset to original colors")
        return {'FINISHED'}

class AETHER_OT_RandomizeTheme(bpy.types.Operator):
    bl_idname = "aether.randomize_theme"
    bl_label = "Random Vibrant Theme"
    bl_description = "Generate a harmonious vibrant random color variation"
    def execute(self, context):
        props = context.scene.aether_rgb_props
        props.r_value = 1.0
        props.g_value = 1.0
        props.b_value = 1.0
        props.hue_value = 0.0
        props.saturation_value = 1.0
        props.value_value = 1.0
        props.color_rotation_value = 0.0
        props.shadows_value = random.uniform(-0.3, 0.5)
        props.brightness_value = random.uniform(1.0, 1.6)
        props.contrast_value = random.uniform(1.0, 1.4)
        props.warmth_value = random.uniform(-0.4, 0.6)
        props.tint_value = random.uniform(-0.3, 0.3)
        props.vibrance_value = random.uniform(0.2, 0.5)
        if random.random() < 0.25:
            props.color_rotation_value = random.uniform(-0.3, 0.3)
        props.saturation_value = random.uniform(1.4, 2.0)
        props.value_value = random.uniform(1.1, 1.6)
        themes = ['red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple', 'pink', 'neutral', 'wild']
        theme = random.choice(themes)
        if theme == 'red':
            props.r_value = random.uniform(1.5, 2.5)
            props.g_value = random.uniform(0.75, 1.3)
            props.b_value = random.uniform(0.75, 1.3)
            props.hue_value = random.uniform(-0.05, 0.05)
            props.saturation_value = random.uniform(1.4, 2.0)
            props.warmth_value += random.uniform(0.3, 0.7)
        elif theme == 'orange':
            props.r_value = random.uniform(1.6, 2.5)
            props.g_value = random.uniform(1.1, 1.8)
            props.b_value = random.uniform(0.7, 1.2)
            props.hue_value = random.uniform(0.04, 0.14)
            props.saturation_value = random.uniform(1.3, 2.0)
            props.warmth_value += random.uniform(0.4, 0.8)
        elif theme == 'yellow':
            props.r_value = random.uniform(1.4, 2.3)
            props.g_value = random.uniform(1.4, 2.3)
            props.b_value = random.uniform(0.7, 1.3)
            props.hue_value = random.uniform(0.07, 0.17)
            props.saturation_value = random.uniform(1.3, 2.0)
            props.warmth_value += random.uniform(0.4, 0.8)
        elif theme == 'green':
            props.r_value = random.uniform(0.7, 1.3)
            props.g_value = random.uniform(1.5, 2.5)
            props.b_value = random.uniform(0.75, 1.4)
            props.hue_value = random.uniform(0.22, 0.42)
            props.saturation_value = random.uniform(1.2, 1.9)
            props.warmth_value += random.uniform(-0.2, 0.2)
        elif theme == 'cyan':
            props.r_value = random.uniform(0.7, 1.3)
            props.g_value = random.uniform(1.4, 2.3)
            props.b_value = random.uniform(1.4, 2.3)
            props.hue_value = random.uniform(0.45, 0.58)
            props.saturation_value = random.uniform(1.3, 2.0)
            props.warmth_value += random.uniform(-0.4, -0.1)
        elif theme == 'blue':
            props.r_value = random.uniform(0.7, 1.2)
            props.g_value = random.uniform(0.8, 1.4)
            props.b_value = random.uniform(1.5, 2.5)
            props.hue_value = random.uniform(0.58, 0.75)
            props.saturation_value = random.uniform(1.2, 1.9)
            props.warmth_value += random.uniform(-0.6, -0.2)
        elif theme == 'purple':
            props.r_value = random.uniform(1.3, 2.2)
            props.g_value = random.uniform(0.7, 1.2)
            props.b_value = random.uniform(1.4, 2.3)
            props.hue_value = random.uniform(0.75, 0.95)
            props.saturation_value = random.uniform(1.3, 2.0)
            props.warmth_value += random.uniform(-0.1, 0.3)
        elif theme == 'pink':
            props.r_value = random.uniform(1.5, 2.4)
            props.g_value = random.uniform(0.8, 1.4)
            props.b_value = random.uniform(1.3, 2.2)
            props.hue_value = random.uniform(-0.06, 0.04)
            props.saturation_value = random.uniform(1.2, 1.8)
            props.warmth_value += random.uniform(0.2, 0.5)
        elif theme == 'neutral':
            props.r_value = random.uniform(0.95, 1.4)
            props.g_value = random.uniform(0.95, 1.4)
            props.b_value = random.uniform(0.95, 1.4)
            props.hue_value = random.uniform(-0.1, 0.1)
            props.saturation_value = random.uniform(0.5, 1.0)
            props.value_value = random.uniform(1.1, 1.6)
        elif theme == 'wild':
            props.r_value = random.uniform(0.8, 2.4)
            props.g_value = random.uniform(0.8, 2.4)
            props.b_value = random.uniform(0.8, 2.4)
            props.hue_value = random.uniform(-0.4, 0.4)
            props.saturation_value = random.uniform(0.9, 2.0)
            props.value_value = random.uniform(0.9, 1.6)
            props.color_rotation_value = random.uniform(-0.6, 0.6)
        refresh_materials(context)
        self.report({'INFO'}, f"Random vibrant {theme.capitalize()} theme applied")
        return {'FINISHED'}

class AETHER_OT_ApplyOriginalColors(bpy.types.Operator):
    bl_idname = "aether.apply_original_colors"
    bl_label = "Apply as Baseline"
    bl_description = "Save current colors as new baseline"
    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                obj["original_colors"] = {}
                store_original_colors(obj)
        props = context.scene.aether_rgb_props
        props.r_value = 1.0
        props.g_value = 1.0
        props.b_value = 1.0
        props.hue_value = 0.0
        props.saturation_value = 1.0
        props.value_value = 1.0
        props.brightness_value = 1.0
        props.contrast_value = 1.0
        props.warmth_value = 0.0
        props.tint_value = 0.0
        props.vibrance_value = 0.0
        props.color_rotation_value = 0.0
        props.shadows_value = 0.0
        self.report({'INFO'}, "Current colors set as new baseline")
        return {'FINISHED'}

class AETHER_OT_PrintCurrentPreset(bpy.types.Operator):
    bl_idname = "aether.print_current_preset"
    bl_label = "Print Preset"
    bl_description = "Print current slider values as preset format (check console)"
    preset_name: bpy.props.StringProperty(name="Preset Name", default="MyPreset")
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "preset_name")
    def execute(self, context):
        props = context.scene.aether_rgb_props
        preset_line = f' "{self.preset_name}": {{'
        preset_line += f'"r": {props.r_value:.2f}, '
        preset_line += f'"g": {props.g_value:.2f}, '
        preset_line += f'"b": {props.b_value:.2f}, '
        preset_line += f'"h": {props.hue_value:.2f}, '
        preset_line += f'"s": {props.saturation_value:.2f}, '
        preset_line += f'"v": {props.value_value:.2f}, '
        preset_line += f'"brightness": {props.brightness_value:.2f}, '
        preset_line += f'"contrast": {props.contrast_value:.2f}, '
        preset_line += f'"warmth": {props.warmth_value:.2f}, '
        preset_line += f'"tint": {props.tint_value:.2f}, '
        preset_line += f'"vibrance": {props.vibrance_value:.2f}, '
        preset_line += f'"rotation": {props.color_rotation_value:.2f}, '
        preset_line += f'"shadows": {props.shadows_value:.2f}'
        preset_line += '},'
        print("\n" + "="*80)
        print("COPY THIS LINE AND PASTE INTO PRESETS DICTIONARY:")
        print("="*80)
        print(preset_line)
        print("="*80 + "\n")
        context.window_manager.clipboard = preset_line
        self.report({'INFO'}, "Preset copied to clipboard + console")
        return {'FINISHED'}

# ===============================================================
# PRESETS
# ===============================================================
PRESETS = {
    "Crimson": {"r": 1.6, "g": 0.7, "b": 0.7, "h": 0.0, "s": 1.3, "v": 1.0, "brightness": 1.0, "contrast": 1.1, "warmth": 0.3, "tint": 0.0, "vibrance": 0.2, "rotation": 0.0},
    "Ruby": {"r": 2.50, "g": 0.00, "b": 0.00, "h": -0.06, "s": 1.77, "v": 0.90, "brightness": 2.00, "contrast": 1.25, "warmth": 0.24, "tint": -0.04, "vibrance": -0.21, "rotation": 0.0},
    "Wine": {"r": 1.5, "g": 0.7, "b": 1.1, "h": 0.03, "s": 1.3, "v": 1.0, "brightness": 1.0, "contrast": 1.15, "warmth": 0.25, "tint": 0.15, "vibrance": 0.15, "rotation": 0.0},
    "Tangerine": {"r": 1.7, "g": 1.1, "b": 0.6, "h": 0.07, "s": 1.4, "v": 1.1, "brightness": 1.1, "contrast": 1.0, "warmth": 0.45, "tint": 0.0, "vibrance": 0.15, "rotation": 0.0},
    "Gold": {"r": 1.60, "g": 1.40, "b": 0.60, "h": 0.12, "s": 1.30, "v": 2.00, "brightness": 2.00, "contrast": 0.85, "warmth": 0.32, "tint": 0.00, "vibrance": 0.10, "rotation": 0.0},
    "Bronze": {"r": 1.4, "g": 1.0, "b": 0.7, "h": 0.10, "s": 1.2, "v": 1.0, "brightness": 1.0, "contrast": 1.1, "warmth": 0.35, "tint": 0.0, "vibrance": 0.15, "rotation": 0.0},
    "Emerald": {"r": 2.50, "g": 2.50, "b": 0.00, "h": 0.25, "s": 1.30, "v": 1.56, "brightness": 1.25, "contrast": 1.03, "warmth": -0.14, "tint": 0.32, "vibrance": -0.10, "rotation": 0.0},
    "Jade": {"r": 0.8, "g": 1.5, "b": 1.0, "h": 0.28, "s": 1.2, "v": 1.0, "brightness": 1.0, "contrast": 1.05, "warmth": -0.15, "tint": 0.0, "vibrance": 0.2, "rotation": 0.0},
    "Lime": {"r": 0.78, "g": 2.50, "b": 0.00, "h": 0.20, "s": 1.40, "v": 2.00, "brightness": 2.00, "contrast": 0.93, "warmth": -0.07, "tint": 0.06, "vibrance": 0.50, "rotation": 0.0},
    "Forest": {"r": 0.7, "g": 1.4, "b": 0.75, "h": 0.33, "s": 1.25, "v": 1.05, "brightness": 1.05, "contrast": 1.15, "warmth": 0.05, "tint": 0.0, "vibrance": 0.2, "rotation": 0.0},
    "Cyan": {"r": 2.50, "g": 2.50, "b": 2.50, "h": 0.50, "s": 1.40, "v": 2.00, "brightness": 1.15, "contrast": 1.00, "warmth": -0.30, "tint": 0.00, "vibrance": 0.25, "rotation": 0.0},
    "Turquoise": {"r": 0.8, "g": 1.4, "b": 1.4, "h": 0.45, "s": 1.3, "v": 1.1, "brightness": 1.05, "contrast": 1.05, "warmth": -0.25, "tint": 0.0, "vibrance": 0.2, "rotation": 0.0},
    "Sapphire": {"r": 2.50, "g": 0.00, "b": 2.47, "h": 0.50, "s": 1.30, "v": 1.05, "brightness": 2.00, "contrast": 0.98, "warmth": -1.00, "tint": 0.00, "vibrance": 0.20, "rotation": 0.0},
    "Cobalt": {"r": 0.7, "g": 1.0, "b": 1.5, "h": 0.60, "s": 1.2, "v": 1.0, "brightness": 1.0, "contrast": 1.05, "warmth": -0.35, "tint": 0.0, "vibrance": 0.15, "rotation": 0.0},
    "Navy": {"r": 0.8, "g": 0.95, "b": 1.5, "h": 0.64, "s": 1.2, "v": 1.0, "brightness": 1.0, "contrast": 1.1, "warmth": -0.35, "tint": 0.0, "vibrance": 0.2, "rotation": 0.0},
    "Amethyst": {"r": 1.2, "g": 0.7, "b": 1.5, "h": 0.78, "s": 1.2, "v": 1.05, "brightness": 1.05, "contrast": 1.05, "warmth": 0.05, "tint": 0.2, "vibrance": 0.25, "rotation": 0.0},
    "Violet": {"r": 2.50, "g": 2.50, "b": 0.00, "h": -0.26, "s": 2.00, "v": 2.00, "brightness": 2.00, "contrast": 1.06, "warmth": 0.03, "tint": 0.07, "vibrance": 0.50, "rotation": 0.0},
    "Magenta": {"r": 1.5, "g": 0.7, "b": 1.3, "h": 0.90, "s": 1.4, "v": 1.1, "brightness": 1.1, "contrast": 1.05, "warmth": 0.1, "tint": 0.3, "vibrance": 0.3, "rotation": 0.0},
    "Pink": {"r": 2.50, "g": 0.04, "b": 2.50, "h": -0.08, "s": 2.00, "v": 2.00, "brightness": 2.00, "contrast": 1.10, "warmth": -0.11, "tint": 0.20, "vibrance": 0.20, "rotation": 0.0},
    "Silver": {"r": 1.20, "g": 0.00, "b": 1.20, "h": -0.50, "s": 0.40, "v": 2.00, "brightness": 2.00, "contrast": 0.84, "warmth": 0.00, "tint": 0.00, "vibrance": -0.20, "rotation": 0.0},
    "Platinum": {"r": 2.50, "g": 0.00, "b": 0.00, "h": 0.50, "s": 0.29, "v": 2.00, "brightness": 1.75, "contrast": 0.71, "warmth": -0.10, "tint": 0.00, "vibrance": -0.47, "rotation": 0.0},
    "Obsidian": {"r": 1.1, "g": 1.0, "b": 1.2, "h": 0.75, "s": 0.8, "v": 0.9, "brightness": 0.9, "contrast": 1.25, "warmth": -0.2, "tint": 0.1, "vibrance": 0.1, "rotation": 0.0},
    "Shadow": {"r": 2.50, "g": 0.00, "b": 0.00, "h": 0.50, "s": 1.30, "v": 1.89, "brightness": 0.81, "contrast": 1.15, "warmth": -0.44, "tint": 0.32, "vibrance": 0.25, "rotation": 0.0},
    "Arcane": {"r": 2.50, "g": 0.00, "b": 0.00, "h": 0.50, "s": 0.00, "v": 1.71, "brightness": 2.00, "contrast": 1.35, "warmth": -0.18, "tint": -0.07, "vibrance": 0.43, "rotation": 0.0},
    "OSRS Phat Red": {"r": 2.2, "g": 0.4, "b": 0.4, "h": 0.0, "s": 1.8, "v": 0.7, "brightness": 0.8, "contrast": 1.2, "warmth": 0.4, "tint": 0.0, "vibrance": 0.3, "rotation": 0.0},
    "OSRS Phat Yellow": {"r": 1.8, "g": 2.0, "b": 0.3, "h": 0.09, "s": 1.8, "v": 1.5, "brightness": 1.5, "contrast": 1.0, "warmth": 0.6, "tint": 0.0, "vibrance": 0.4, "rotation": 0.0},
    "OSRS Phat Green": {"r": 0.4, "g": 2.2, "b": 0.4, "h": 0.33, "s": 1.8, "v": 1.4, "brightness": 1.4, "contrast": 1.1, "warmth": 0.0, "tint": 0.0, "vibrance": 0.4, "rotation": 0.0},
    "OSRS Phat Blue": {"r": 0.3, "g": 0.3, "b": 2.2, "h": 0.66, "s": 1.7, "v": 0.9, "brightness": 0.9, "contrast": 1.2, "warmth": -0.5, "tint": 0.0, "vibrance": 0.3, "rotation": 0.0},
    "OSRS Phat Purple": {"r": 1.5, "g": 0.4, "b": 2.0, "h": 0.80, "s": 1.8, "v": 1.3, "brightness": 1.3, "contrast": 1.1, "warmth": 0.1, "tint": 0.2, "vibrance": 0.4, "rotation": 0.0},
}

# ===============================================================
# PROPERTIES
# ===============================================================
class RGBProperties(bpy.types.PropertyGroup):
    def update_trigger(self, context):
        refresh_materials(context)
    r_value: bpy.props.FloatProperty(name="R", default=1.0, min=0.0, max=2.5, update=update_trigger)
    g_value: bpy.props.FloatProperty(name="G", default=1.0, min=0.0, max=2.5, update=update_trigger)
    b_value: bpy.props.FloatProperty(name="B", default=1.0, min=0.0, max=2.5, update=update_trigger)
    hue_value: bpy.props.FloatProperty(name="Hue", default=0.0, min=-0.5, max=0.5, update=update_trigger)
    saturation_value: bpy.props.FloatProperty(name="Saturation", default=1.0, min=0.0, max=2.0, update=update_trigger)
    value_value: bpy.props.FloatProperty(name="Value", default=1.0, min=0.1, max=3.0, update=update_trigger)
    brightness_value: bpy.props.FloatProperty(name="Brightness", default=1.0, min=0.1, max=3.0, update=update_trigger)
    contrast_value: bpy.props.FloatProperty(name="Contrast", default=1.0, min=0.5, max=2.0, update=update_trigger)
    warmth_value: bpy.props.FloatProperty(name="Warmth", default=0.0, min=-1.0, max=1.0, update=update_trigger)
    tint_value: bpy.props.FloatProperty(name="Tint", default=0.0, min=-1.0, max=1.0, update=update_trigger)
    vibrance_value: bpy.props.FloatProperty(name="Vibrance", default=0.0, min=-0.5, max=0.5, update=update_trigger)
    color_rotation_value: bpy.props.FloatProperty(name="Color Rotation", default=0.0, min=-1.0, max=1.0, update=update_trigger)
    shadows_value: bpy.props.FloatProperty(name="Shadows", default=0.0, min=-1.0, max=1.0, description="Positive: crush to black (darker), Negative: lift shadows (brighter dark areas)", update=update_trigger)
    alpha_value: bpy.props.FloatProperty(name="Opacity", default=100.0, min=0.0, max=100.0, update=update_trigger)

# ===============================================================
# UI PANEL
# ===============================================================
class AETHER_PT_ColorTint(bpy.types.Panel):
    bl_label = "Aether Material Engine"
    bl_idname = "AETHER_PT_color_tint"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RSPS ADDON'
    bl_parent_id = "OBJECT_PT_rs_pmn_texturing"
    bl_options = {'DEFAULT_CLOSED'}
    def draw(self, context):
        layout = self.layout
        props = context.scene.aether_rgb_props
        obj = context.active_object
        if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
            box = layout.box()
            box.alert = True
            box.label(text="EDIT MODE: Only selected faces affected", icon='FACESEL')
        layout.operator("aether.optimize_shading", text="⚡ Optimize OSRS Shading", icon='SHADING_SOLID')
        box = layout.box()
        box.label(text="Color Presets", icon='COLOR')
        col = box.column(align=True)
        row = col.row(align=True)
        row.label(text="Reds:")
        for name in ["Crimson", "Ruby", "Wine"]:
            op = row.operator("aether.apply_preset", text=name)
            op.preset_name = name
        row = col.row(align=True)
        row.label(text="Oranges:")
        for name in ["Tangerine", "Gold", "Bronze"]:
            op = row.operator("aether.apply_preset", text=name)
            op.preset_name = name
        row = col.row(align=True)
        row.label(text="Greens:")
        for name in ["Emerald", "Jade", "Lime", "Forest"]:
            op = row.operator("aether.apply_preset", text=name)
            op.preset_name = name
        row = col.row(align=True)
        row.label(text="Blues:")
        for name in ["Cyan", "Turquoise", "Sapphire", "Cobalt", "Navy"]:
            op = row.operator("aether.apply_preset", text=name)
            op.preset_name = name
        row = col.row(align=True)
        row.label(text="Purples:")
        for name in ["Amethyst", "Violet", "Magenta", "Pink"]:
            op = row.operator("aether.apply_preset", text=name)
            op.preset_name = name
        row = col.row(align=True)
        row.label(text="Neutral:")
        for name in ["Silver", "Platinum", "Obsidian"]:
            op = row.operator("aether.apply_preset", text=name)
            op.preset_name = name
        row = col.row(align=True)
        row.label(text="Special:")
        for name in ["Shadow", "Arcane"]:
            op = row.operator("aether.apply_preset", text=name)
            op.preset_name = name
        row = col.row(align=True)
        row.label(text="OSRS Partyhats:")
        for name in ["OSRS Phat Red", "OSRS Phat Yellow", "OSRS Phat Green", "OSRS Phat Blue", "OSRS Phat Purple"]:
            op = row.operator("aether.apply_preset", text=name.split()[-1])
            op.preset_name = name
        basic = layout.box()
        basic.label(text="Base Theme", icon='COLORSET_01_VEC')
        row = basic.row(align=True)
        row.prop(props, "r_value", slider=True)
        row.prop(props, "g_value", slider=True)
        row.prop(props, "b_value", slider=True)
        row = basic.row(align=True)
        row.prop(props, "hue_value", slider=True)
        row.prop(props, "saturation_value", slider=True)
        basic.prop(props, "value_value", slider=True)
        atmos = layout.box()
        atmos.label(text="Atmosphere", icon='SHADING_RENDERED')
        atmos.prop(props, "brightness_value", slider=True)
        atmos.prop(props, "contrast_value", slider=True)
        row = atmos.row(align=True)
        row.prop(props, "warmth_value", slider=True)
        row.prop(props, "tint_value", slider=True)
        atmos.prop(props, "vibrance_value", slider=True)
        atmos.prop(props, "color_rotation_value", slider=True)
        # Shadows control
        shadows_box = layout.box()
        shadows_box.label(text="Shadows Control", icon='LIGHT')
        shadows_box.prop(props, "shadows_value", slider=True)
        layout.separator()
        row = layout.row(align=True)
        row.operator("aether.apply_original_colors", icon='CHECKMARK')
        row.operator("aether.reset_materials", icon='LOOP_BACK')
        row = layout.row(align=True)
        row.operator("aether.randomize_theme", text="Random Vibrant Theme", icon='QUESTION')
        row.operator("aether.print_current_preset", text="Print Preset", icon='COPYDOWN')
        layout.prop(props, "alpha_value", slider=True)

# ===============================================================
# REGISTRATION
# ===============================================================
classes = (
    RGBProperties,
    AETHER_OT_OptimizeShading,
    AETHER_OT_ApplyPreset,
    AETHER_OT_ResetMaterials,
    AETHER_OT_RandomizeTheme,
    AETHER_OT_ApplyOriginalColors,
    AETHER_OT_PrintCurrentPreset,
    AETHER_PT_ColorTint,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.aether_rgb_props = bpy.props.PointerProperty(type=RGBProperties)

def unregister():
    del bpy.types.Scene.aether_rgb_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
