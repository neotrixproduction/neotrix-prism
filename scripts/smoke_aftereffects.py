"""Exercise the installed Neotrix CEP transport with the upstream AE adapter."""
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEOTRIX_USER_DIR"] = str(ROOT / "artifacts/aftereffects-prefs")
from PySide6.QtWidgets import QApplication
application = QApplication([])
from neotrix_prism.integration import get_core
from neotrix_prism.versions import save_next
core = get_core("AfterEffects", no_ui=True)
source = ROOT / "artifacts/app-smoke/AfterEffects/Neotrix_QA_V0001.aep"
actual = core.appPlugin.getCurrentFileName(core)
assert Path(actual) == source, actual
def save(path):
    return core.appPlugin.saveScene(core, path.replace("\\", "/"))
from neotrix_prism.project_metadata import StageStore
from neotrix_prism.integration import save_version_dialog
from PySide6.QtWidgets import QMessageBox
store=StageStore(source.parent)
store.save([source],'compositing',store.load()['fingerprint'])
QMessageBox.question=lambda *args:QMessageBox.Save
destination=save_version_dialog(core,expected_source=str(source))
assert destination and store.load()['assignments'][destination.name]=='compositing'
core.appPlugin.sendCmd("app.open(new File(" + json.dumps(destination.as_posix()) + "));")
reply = core.appPlugin.sendCmd("app.project.item(1).numLayers;").decode()
assert reply == "2", reply
assert Path(core.appPlugin.getCurrentFileName(core)) == destination
(source.parent / "result.json").write_text(json.dumps({"application": "After Effects 2026", "saved": destination.name,
    "unsaved_changes_preserved": True, "reopened": True, "stage_inherited":True, "transport": "installed Neotrix CEP panel"}, indent=2))
print("NEOTRIX_AFTEREFFECTS_SAVE_REOPEN_PASS", destination.name)
