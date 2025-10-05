# ui.py
import bpy
import os
from .dat_exporter import export_dat, detect_model_type
# --- OPERATOR ---
class EXPORTER_OT_export_model(bpy.types.Operator):
    """Exports selected objects to the chosen format with a specific preset."""
    bl_idname = "export.rsps_model"
    bl_label = "Export Selected Model(s)"
    bl_options = {'REGISTER', 'UNDO'}
    export_preset: bpy.props.StringProperty(default='DEFAULT')
    export_format: bpy.props.StringProperty(default='DAT')
    auto_detect: bpy.props.BoolProperty(default=False)
    def execute(self, context):
        scene = context.scene
        output_dir = scene.exporter_output_dir
       
        if not output_dir:
            self.report({'WARNING'}, "Please select an output directory.")
            return {'CANCELLED'}
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        selected_objects = context.selected_objects
        exported_count = 0
       
        for obj in selected_objects:
            if obj.type == 'MESH':
                # Determine the export preset
                export_preset = self.export_preset
               
                # Auto-detect model type if enabled (for drop model transformations)
                detected_type = 'UNKNOWN'
                if self.auto_detect:
                    detected_type = detect_model_type(obj)
                    if detected_type != 'UNKNOWN':
                        print(f"Auto-detected model type: {detected_type}")
                        # For weight-based, use detected type as preset
                        if self.export_preset == 'DEFAULT':
                            export_preset = detected_type
                    else:
                        self.report({'WARNING'}, f"Could not auto-detect model type for '{obj.name}'.")
               
                filename = f"{obj.name}.{self.export_format.lower()}"
                filepath = os.path.join(output_dir, filename)
               
                if self.export_format == 'DAT':
                    # For CUSTOM_PRIORITY with auto_detect, pass the detected type for drop transformations
                    if self.export_preset == 'CUSTOM_PRIORITY' and self.auto_detect and detected_type != 'UNKNOWN':
                        # Export normal with CUSTOM_PRIORITY preset
                        from .dat_exporter import _export_core
                        _export_core(filepath, obj, 'CUSTOM_PRIORITY', drop_mode=False)
                       
                        # Export drop with detected type transformations
                        drop_filepath = filepath.replace('.dat', '_drop.dat') if filepath.endswith('.dat') else filepath + '_drop.dat'
                        _export_core(drop_filepath, obj, detected_type, drop_mode=True)
                        print(f"Exported CUSTOM_PRIORITY normal + {detected_type} drop model")
                    else:
                        export_dat(filepath, obj, export_preset=export_preset)
               
                exported_count += 1
       
        if exported_count > 0:
            self.report({'INFO'}, f"Exported {exported_count} models to {output_dir}.")
        else:
            self.report({'WARNING'}, "No mesh objects were selected for export.")
        return {'FINISHED'}
# --- PANEL ---
class VIEW3D_PT_rsps_model_io(bpy.types.Panel):
    """The UI panel for model import/export in the 3D View."""
    bl_label = "Model Exporter and Model Importer"
    bl_idname = "VIEW3D_PT_rsps_model_io"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RSPS ADDON'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 3
    def draw(self, context):
        layout = self.layout
        scene = context.scene
       
        # --- EXPORT SECTION ---
        export_box = layout.box()
        export_box.label(text="Step 3: Export Model", icon='EXPORT')
       
        if context.mode == 'OBJECT':
            export_box.prop(scene, "exporter_output_dir")
            export_box.separator()
            # --- TWO MAIN EXPORT BUTTONS ---
            col = export_box.column(align=True)
            col.label(text="DAT Export (Auto-Detect & Drop):")
           
            # Button 1: Weight-Based Auto-Detect
            op = col.operator("export.rsps_model", text="Export DAT (Weight-Based)", icon='WPAINT_HLT')
            op.export_preset = 'DEFAULT'
            op.export_format = 'DAT'
            op.auto_detect = True
           
            col.label(text="Needs: VSKIN weights only")
            col.label(text="Automatically creates: Priorities & TSKINs")
            col.label(text="Detects: Head, Body, Gloves, Pants, Boots,")
            col.label(text=" Sword, Shield, Necklace, Cape")
            col.label(text="Creates both normal and _drop.dat files")
           
            export_box.separator()
           
            # Button 2: Color-Based Custom
            col = export_box.column(align=True)
            col.label(text="DAT Export (Color Layers & Drop):")
           
            op = col.operator("export.rsps_model", text="Export DAT (Custom Color)", icon='BRUSH_DATA')
            op.export_preset = 'CUSTOM_PRIORITY'
            op.export_format = 'DAT'
            op.auto_detect = True
           
            col.label(text="Needs: RSPRI (priorities), RSTSKIN (texture skins),")
            col.label(text=" VSKIN (vertex groups) vertex color layers")
            col.label(text="For: Shield, Cape, NPCs & custom models")
            col.label(text="Auto-detects model type for drop files")
            col.label(text="Creates both normal and _drop.dat files")
            # --- RS STYLE BUTTON ---
            export_box.separator()
            export_box.operator("rsps.setup_runescape_style", text="Make Render RS Style", icon='RENDER_STILL')
        else:
            box = export_box.box()
            box.label(text="Switch to Object Mode to export.", icon='INFO')
            box.operator("object.mode_set", text="Enter Object Mode").mode = 'OBJECT'
       
        # --- IMPORT SECTION ---
        import_box = layout.box()
        import_box.label(text="Import Models", icon='IMPORT')
       
        row = import_box.row(align=True)
        row.operator("import_scene.rs_317_model", text="Import 317/OSRS Model", icon='IMPORT')
        row.operator("import_scene.rs_667_model", text="Import 667 Model", icon='IMPORT')
# A tuple containing all classes from this file for registration by __init__.py
classes = (
    EXPORTER_OT_export_model,
    VIEW3D_PT_rsps_model_io,
)