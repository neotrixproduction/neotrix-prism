"""Run with Blender --background --factory-startup --python. Test files only."""
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "runtime/Lib"))
os.environ["NEOTRIX_USER_DIR"] = str(ROOT / "artifacts/blender-prefs")
from PySide6.QtWidgets import QApplication
app = QApplication([])
import bpy
from neotrix_prism.integration import get_core
from neotrix_prism.versions import save_next

directory = ROOT / "artifacts/app-smoke/Blender"
directory.mkdir(parents=True, exist_ok=True)
source = directory / "Neotrix_QA_v001.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(source))
core = get_core("Blender", no_ui=True)
cube = bpy.data.objects["Cube"]
cube.location.x = 4.25
def save(path):
    core.appPlugin.saveScene(core, path)
    return Path(path).is_file()
from neotrix_prism.project_metadata import StageStore
from neotrix_prism.integration import save_version_dialog
from PySide6.QtWidgets import QMessageBox
store=StageStore(directory)
store.save([source],'lighting',store.load()['fingerprint'])
QMessageBox.question=lambda *args:QMessageBox.Save
destination=save_version_dialog(core,expected_source=str(source))
assert destination and store.load()['assignments'][destination.name]=='lighting'
bpy.ops.wm.open_mainfile(filepath=str(destination))
assert bpy.data.objects["Cube"].location.x == 4.25
assert source.exists()
(directory / "result.json").write_text(json.dumps({"application": bpy.app.version_string, "python": sys.version,
    "saved": destination.name, "unsaved_changes_preserved": True, "reopened": True, "stage_inherited":True}, indent=2))
print("NEOTRIX_BLENDER_SAVE_REOPEN_PASS", destination.name)
