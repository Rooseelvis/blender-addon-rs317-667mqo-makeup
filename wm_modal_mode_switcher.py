# wm_modal_mode_switcher.py
import bpy
import time
import bmesh

class ModalModeWatcher(bpy.types.Operator):
    """Watch for mode changes and auto-sync PMN/UV (ESC to stop)"""
    bl_idname = "wm.modal_mode_watcher"
    bl_label = "Modal Mode Watcher with Auto Sync"

    _timer = None
    last_mode = None
    last_sync_time = 0.0

    def modal(self, context, event):
        # If the master toggle in the UI is turned off, cancel the operator
        if not context.scene.rs_pmn.auto_sync_enabled:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            current_mode = context.mode

            if current_mode != self.last_mode:
                self.last_mode = current_mode

                if current_mode in {"EDIT_MESH", "OBJECT"}:
                    now = time.time()
                    if now - self.last_sync_time > 0.2:
                        self.last_sync_time = now
                        # Use a timer to prevent context issues
                        bpy.app.timers.register(
                            lambda: self.sync_all_materials(current_mode),
                            first_interval=0.15
                        )

        if event.type == 'ESC' and event.value == 'PRESS':
            self.cancel(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def sync_all_materials(self, mode):
        """Syncs PMN for ALL PMN materials on the active object using BMesh."""
        obj = bpy.context.active_object
        if not obj or obj.type != 'MESH' or not any(ms.material for ms in obj.material_slots):
            return None

        # --- Store original state ---
        original_active_mat_index = obj.active_material_index
        original_mode = obj.mode
        
        # Must be in edit mode for bmesh operations on the active mesh
        if original_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        # Use bmesh to get the original selection without operators
        bm = bmesh.from_edit_mesh(obj.data)
        original_selection = {f.index for f in bm.faces if f.select}
        
        try:
            # --- Iterate and sync each material ---
            for i, mat_slot in enumerate(obj.material_slots):
                if mat_slot.material and hasattr(mat_slot.material, 'rs_pmn_mat'):
                    obj.active_material_index = i
                    
                    # Select faces assigned to this material
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bpy.ops.object.material_slot_select()
                    
                    # If any faces were selected for this material, sync them
                    if obj.data.total_face_sel > 0:
                        bpy.ops.rs_pmn.sync_pmn_uv()

        finally:
            # --- Restore original state ---
            bpy.ops.mesh.select_all(action='DESELECT')
            
            # Re-select the original faces using bmesh
            bm.select_flush(False) # Clear selection states
            for f in bm.faces:
                if f.index in original_selection:
                    f.select_set(True)
            
            bmesh.update_edit_mesh(obj.data)
            
            # Restore material and mode
            obj.active_material_index = original_active_mat_index
            if obj.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
                
        return None

    def execute(self, context):
        context.scene.rs_pmn.auto_sync_enabled = True
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.2, window=context.window)
        wm.modal_handler_add(self)
        self.last_mode = context.mode
        self.report({'INFO'}, "Auto PMN Sync Started.")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.scene.rs_pmn.auto_sync_enabled = False
        
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None
        self.report({'INFO'}, "Auto PMN Sync Stopped.")
        
        # Redraw the UI to update the button's appearance
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'CANCELLED'}

# A tuple containing all classes from this file to be imported by __init__.py
classes = (
    ModalModeWatcher,
)