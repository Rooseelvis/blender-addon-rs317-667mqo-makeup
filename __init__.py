# __init__.py

bl_info = {
    "name": "RSPS TOOLKIT",
    "blender": (4, 5, 0),
    "category": "Mesh",
    "author": "Epic Game Dev",
    "version": (7, 7, 0),  # Version bump for separate importers
    "description": "A complete suite for weighting, texturing, and exporting game models with separate 317 and 667 importers.",
    "location": "3D Viewport > N-Panel > RSPS TOOLKIT",
    "support": "COMMUNITY",
}

import bpy
import bpy.utils.previews

# Import all classes and functions from the other modules
from . import weighter
from . import ui
from . import pmn_texturing
from . import wm_modal_mode_switcher
from . import priorities
from . import render_style
from . import tskins
from . import aether_materials

# Import importers conditionally to avoid circular imports
try:
    from . import importer_317
    from . import importer_667
    has_importers = True
except ImportError as e:
    print(f"Warning: Could not import model importers: {e}")
    has_importers = False

# A single list of all classes from all modules to register
if has_importers:
    classes = (
        *weighter.classes,
        *ui.classes,
        *pmn_texturing.classes,
        *wm_modal_mode_switcher.classes,
        *priorities.classes,
        *tskins.classes,
        *render_style.classes,
        *aether_materials.classes,
        *importer_317.classes,
        *importer_667.classes,
    )
else:
    classes = (
        *weighter.classes,
        *ui.classes,
        *pmn_texturing.classes,
        *wm_modal_mode_switcher.classes,
        *priorities.classes,
        *tskins.classes,
        *render_style.classes,
        *aether_materials.classes,
    )

weight_draw_handler = None
priority_overlay_handler = None
priority_text_handler = None
tskin_overlay_handler = None
tskin_text_handler = None

def register():
    """Register all parts of the addon."""
    global weight_draw_handler, priority_overlay_handler, priority_text_handler, tskin_overlay_handler, tskin_text_handler
    
    # Register all classes FIRST
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # THEN register scene properties AFTER the classes are registered
    bpy.types.Scene.show_weight_overlay = bpy.props.BoolProperty(
        name="Show Weight Values", 
        default=False,
        update=weighter.force_viewport_redraw
    )
    bpy.types.Scene.exporter_output_dir = bpy.props.StringProperty(
        name="Output Directory", description="Directory to export files",
        default="", subtype='DIR_PATH', maxlen=1024
    )
    bpy.types.Scene.exporter_format = bpy.props.EnumProperty(
        name="Format", description="Choose the export file format",
        items=[('DAT', "DAT", "Export as .dat")], default='DAT'
    )
    bpy.types.Scene.rsps_priority_to_apply = bpy.props.IntProperty(
        name="Priority", description="Priority value to apply to selected faces (0-255)",
        default=10, min=0, max=255
    )
    bpy.types.Scene.rsps_show_priority_visuals = bpy.props.BoolProperty(
        name="Show Priority Visuals", description="Toggles a colored overlay for face priorities",
        default=False, update=weighter.force_viewport_redraw
    )
    
    # TSKIN properties
    bpy.types.Scene.rsps_tskin_to_apply = bpy.props.IntProperty(
        name="TSKIN Group", description="Group value to apply to selected faces (0-255)",
        default=0, min=0, max=255
    )
    bpy.types.Scene.rsps_show_tskin_visuals = bpy.props.BoolProperty(
        name="Show TSKIN Visuals", description="Toggles colored overlay for face TSKIN groups",
        default=False, update=weighter.force_viewport_redraw
    )
    
    # PMN properties
    bpy.types.Scene.rs_pmn = bpy.props.PointerProperty(type=pmn_texturing.RS_Scene_PropertyGroup)
    bpy.types.Material.rs_pmn_mat = bpy.props.PointerProperty(type=pmn_texturing.RS_Material_PropertyGroup)
    
    # Register Aether properties
    bpy.types.Object.rgb_props = bpy.props.PointerProperty(type=aether_materials.RGBProperties)
    bpy.types.Scene.aether_rgb_props = bpy.props.PointerProperty(type=aether_materials.RGBProperties)
    
    if "main" not in pmn_texturing.preview_collections:
        pmn_texturing.preview_collections["main"] = bpy.utils.previews.new()
        
    # Add draw handlers with proper wrapper functions
    def weight_draw_wrapper():
        weighter.draw_weights_callback(None, bpy.context)
    
    def priority_overlay_wrapper():
        priorities.draw_priority_overlay(bpy.context)
    
    def priority_text_wrapper():
        priorities.draw_priority_text(bpy.context)
    
    def tskin_overlay_wrapper():
        tskins.draw_tskin_overlay(bpy.context)
    
    def tskin_text_wrapper():
        tskins.draw_tskin_text(bpy.context)
    
    weight_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
        weight_draw_wrapper, (), 'WINDOW', 'POST_PIXEL'
    )
    priority_overlay_handler = bpy.types.SpaceView3D.draw_handler_add(
        priority_overlay_wrapper, (), 'WINDOW', 'POST_VIEW'
    )
    priority_text_handler = bpy.types.SpaceView3D.draw_handler_add(
        priority_text_wrapper, (), 'WINDOW', 'POST_PIXEL'
    )
    tskin_overlay_handler = bpy.types.SpaceView3D.draw_handler_add(
        tskin_overlay_wrapper, (), 'WINDOW', 'POST_VIEW'
    )
    tskin_text_handler = bpy.types.SpaceView3D.draw_handler_add(
        tskin_text_wrapper, (), 'WINDOW', 'POST_PIXEL'
    )
    
    # NEW: Add importers to file menu (only if available)
    if has_importers:
        bpy.types.TOPBAR_MT_file_import.append(importer_317.menu_func_import_317)
        bpy.types.TOPBAR_MT_file_import.append(importer_667.menu_func_import_667)
        print("✅ RSPS TOOLKIT with Separate 317 & 667 Importers registered!")
    else:
        print("✅ RSPS TOOLKIT registered (importers not available)!")

def unregister():
    """Unregister all parts of the addon."""
    global weight_draw_handler, priority_overlay_handler, priority_text_handler, tskin_overlay_handler, tskin_text_handler
    
    # NEW: Remove importers from file menu (only if available)
    if has_importers:
        try:
            bpy.types.TOPBAR_MT_file_import.remove(importer_317.menu_func_import_317)
            bpy.types.TOPBAR_MT_file_import.remove(importer_667.menu_func_import_667)
        except:
            pass
    
    # Remove draw handlers first
    if weight_draw_handler:
        bpy.types.SpaceView3D.draw_handler_remove(weight_draw_handler, 'WINDOW')
        weight_draw_handler = None
    if priority_overlay_handler:
        bpy.types.SpaceView3D.draw_handler_remove(priority_overlay_handler, 'WINDOW')
        priority_overlay_handler = None
    if priority_text_handler:
        bpy.types.SpaceView3D.draw_handler_remove(priority_text_handler, 'WINDOW')
        priority_text_handler = None
    if tskin_overlay_handler:
        bpy.types.SpaceView3D.draw_handler_remove(tskin_overlay_handler, 'WINDOW')
        tskin_overlay_handler = None
    if tskin_text_handler:
        bpy.types.SpaceView3D.draw_handler_remove(tskin_text_handler, 'WINDOW')
        tskin_text_handler = None
    
    pcoll = pmn_texturing.preview_collections.get("main")
    if pcoll: bpy.utils.previews.remove(pcoll)
    pmn_texturing.preview_collections.clear()
    
    # Clean up properties
    try:
        del bpy.types.Scene.show_weight_overlay
        del bpy.types.Scene.exporter_output_dir
        del bpy.types.Scene.exporter_format
        del bpy.types.Scene.rsps_priority_to_apply
        del bpy.types.Scene.rsps_show_priority_visuals
        del bpy.types.Scene.rsps_tskin_to_apply
        del bpy.types.Scene.rsps_show_tskin_visuals
        del bpy.types.Scene.rs_pmn
        del bpy.types.Material.rs_pmn_mat
        del bpy.types.Object.rgb_props
        del bpy.types.Scene.aether_rgb_props
    except AttributeError: pass
    
    # Unregister classes LAST
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    print("✅ RSPS TOOLKIT unregistered!")