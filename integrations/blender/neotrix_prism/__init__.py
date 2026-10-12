"""Separate Blender add-on; uses upstream Prism's adapter without replacing it."""
bl_info = {"name": "Neotrix Prism", "author": "Neotrix", "version": (0, 1, 0),
           "blender": (5, 2, 0), "location": "3D View > Sidebar > Neotrix",
           "description": "Projects, current-document version saves and production tools", "category": "Pipeline"}
import json
import os
import sys
from pathlib import Path
import bpy

ROOT = Path(json.loads((Path(__file__).parent / "installation.json").read_text())["root"])
CORE = None
APP = None


def core():
    global CORE, APP
    # Qt/pywin32 binaries must match the host interpreter.
    runtime = ROOT / "runtime"
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError("This package supports Blender's Python 3.13 runtime. Use the desktop explorer for this Blender version.")
    sys.path.insert(0, str(runtime / "Lib"))
    sys.path.insert(0, str(ROOT))
    from PySide6.QtWidgets import QApplication
    APP = QApplication.instance() or QApplication([])
    from neotrix_prism.integration import get_core
    CORE = CORE or get_core("Blender", no_ui=bpy.app.background)
    return CORE


class NEOTRIX_OT_explorer(bpy.types.Operator):
    bl_idname = "neotrix_prism.explorer"
    bl_label = "Explore Projects"
    def execute(self, context):
        try:
            core().neotrixBrowser()
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
        return {"FINISHED"}


class NEOTRIX_OT_save(bpy.types.Operator):
    bl_idname = "neotrix_prism.save_version"
    bl_label = "Save New Version"
    def execute(self, context):
        try:
            adapter_core = core()
            from neotrix_prism.integration import save_version_dialog
            save_version_dialog(adapter_core)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
        return {"FINISHED"}


class NEOTRIX_OT_tools(bpy.types.Operator):
    bl_idname = "neotrix_prism.tools"
    bl_label = "Production Tools"
    def execute(self, context):
        try:
            core().stateManager()
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
        return {"FINISHED"}


class NEOTRIX_PT_workspace(bpy.types.Panel):
    bl_label = "Neotrix Prism"
    bl_idname = "NEOTRIX_PT_workspace"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Neotrix"
    def draw(self, context):
        layout = self.layout
        layout.label(text="Your creative workspace", icon="FUND")
        box = layout.box()
        box.label(text="PROJECTS", icon="FILE_FOLDER")
        box.operator("neotrix_prism.explorer", icon="VIEWZOOM")
        box = layout.box()
        box.label(text="WORKING VERSION", icon="FILE_BLEND")
        box.operator("neotrix_prism.save_version", icon="FILE_TICK")
        box = layout.box()
        box.label(text="PRODUCTION", icon="NODETREE")
        box.operator("neotrix_prism.tools", icon="RENDER_STILL")


CLASSES = [NEOTRIX_OT_explorer, NEOTRIX_OT_save, NEOTRIX_OT_tools, NEOTRIX_PT_workspace]


def pump():
    if APP:
        APP.processEvents()
    return 0.05


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    if not bpy.app.background:
        bpy.app.timers.register(pump, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(pump):
        bpy.app.timers.unregister(pump)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
