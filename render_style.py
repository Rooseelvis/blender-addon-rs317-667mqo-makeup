# render_style.py
import bpy
import bmesh
from mathutils import Vector

class RSPS_OT_setup_runescape_style(bpy.types.Operator):
    """Sets up the Blender scene to mimic Old School RuneScape rendering style in Eevee Next."""
    bl_idname = "rsps.setup_runescape_style"
    bl_label = "Make Render RS Style"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        
        # Set render engine to Eevee Next
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
        
        # Eevee Next settings for stylized look (strict OSRS: no RT, no AO)
        scene.eevee.use_raytracing = False  # No raytracing for true OSRS flatness
        scene.eevee.use_gtao = False  # No AO for minimal shadows
        
        # Remove existing lights if any (optional)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT':
                bpy.data.objects.remove(obj, do_unlink=True)
        
        # Add Sun light
        bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))
        sun = context.active_object
        sun.data.energy = 5.0
        sun.data.color = (1.0, 0.95, 0.85)  # Slight warm tone
        sun.data.angle = 0.5  # Soft shadows
        
        # Rotate sun to point downwards
        sun.rotation_euler = (1.0, 0, -0.785)  # Adjust as needed
        
        # Compute light direction from sun
        sun_matrix = sun.matrix_world
        light_dir_world = -(sun_matrix.to_3x3() @ Vector((0, 0, 1))).normalized()
        
        # Set up World (simple sky gradient-like)
        world = bpy.data.worlds.new(name="RS_Sky")
        world.use_nodes = True
        bg_node = world.node_tree.nodes.get('Background')
        bg_node.inputs[0].default_value = (0.53, 0.81, 0.92, 1.0)  # RS sky blue
        bg_node.inputs[1].default_value = 1.0  # Strength
        scene.world = world
        
        # Create Toon Shader Material (Simple cel-shader)
        mat = bpy.data.materials.new(name="RS_Toon")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        
        # Nodes
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (400, 0)
        
        diffuse = nodes.new(type='ShaderNodeBsdfDiffuse')
        diffuse.location = (0, 0)
        diffuse.inputs['Color'].default_value = (0.8, 0.8, 0.8, 1.0)  # Base color
        diffuse.inputs['Roughness'].default_value = 1.0  # Fully diffuse
        
        # Simple cel ramp: 2-step (lit/shadow)
        ramp = nodes.new(type='ShaderNodeValToRGB')
        ramp.location = (-200, 0)
        ramp.color_ramp.elements[0].color = (0.2, 0.2, 0.2, 1.0)  # Shadow color
        ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)  # Lit color
        ramp.color_ramp.elements[1].position = 0.45  # Threshold for hard shadow
        
        # Fixed light direction
        combine_xyz = nodes.new(type='ShaderNodeCombineXYZ')
        combine_xyz.location = (-400, 100)
        combine_xyz.inputs[0].default_value = light_dir_world.x
        combine_xyz.inputs[1].default_value = light_dir_world.y
        combine_xyz.inputs[2].default_value = light_dir_world.z
        
        normal = nodes.new(type='ShaderNodeNormal')
        normal.location = (-400, -100)
        
        dot = nodes.new(type='ShaderNodeVectorMath')
        dot.location = (-200, -100)
        dot.operation = 'DOT_PRODUCT'
        
        # Connect nodes
        links.new(combine_xyz.outputs['Vector'], dot.inputs[0])
        links.new(normal.outputs['Normal'], dot.inputs[1])
        links.new(dot.outputs['Value'], ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'], diffuse.inputs['Color'])
        links.new(diffuse.outputs['BSDF'], output.inputs['Surface'])
        
        # Apply material and shading to selected objects
        selected = context.selected_objects
        if not selected:
            bpy.ops.object.select_all(action='SELECT')
            selected = context.selected_objects
        
        for obj in selected:
            if obj.type == 'MESH':
                if len(obj.data.materials) == 0:
                    obj.data.materials.append(mat)
                else:
                    obj.data.materials[0] = mat
                
                context.view_layer.objects.active = obj
                bpy.ops.object.shade_flat()

        # ---- START: YOUR WORKING OUTLINE CODE ----
        # Enable Freestyle for outlines
        scene.render.use_freestyle = True
        
        # Ensure there is at least one render layer and lineset
        # This part is a bit of a legacy access method
        if scene.view_layers:
            view_layer = scene.view_layers[0] # Get the first view layer
            if not view_layer.freestyle_settings.linesets:
                 view_layer.freestyle_settings.linesets.new("FreestyleLineSet")
            
            lineset = view_layer.freestyle_settings.linesets[0]
            lineset.select_silhouette = True
            lineset.select_border = False
            lineset.select_crease = False
            lineset.select_edge_mark = False
            
            # Access the linestyle and set thickness
            linestyle = lineset.linestyle
            linestyle.thickness = 2.0
            linestyle.color = (0, 0, 0)
        # ---- END: YOUR WORKING OUTLINE CODE ----
        
        # Set viewport to Material Preview
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'
                        space.shading.light = 'STUDIO'
        
        self.report({'INFO'}, "RuneScape style setup complete! Adjust the base color in the Toon material.")
        return {'FINISHED'}

classes = (
    RSPS_OT_setup_runescape_style,
)