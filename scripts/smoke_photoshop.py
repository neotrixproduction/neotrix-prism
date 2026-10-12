"""Create and close only a dedicated Photoshop QA document."""
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEOTRIX_USER_DIR"] = str(ROOT / "artifacts/photoshop-prefs")
from PySide6.QtWidgets import QApplication
app = QApplication([])
import win32com.client
ps = win32com.client.Dispatch("Photoshop.Application")
original = None
try:
    original = ps.ActiveDocument
except Exception:
    pass
document = None
try:
    document = ps.Documents.Add(128, 128, 72, "Neotrix QA")
    directory = ROOT / "artifacts/app-smoke/Photoshop"
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "Neotrix_QA_v001.psd"
    document.SaveAs(str(source))
    from neotrix_prism.integration import get_core
    from neotrix_prism.versions import save_next
    core = get_core("Photoshop", no_ui=True)
    document.ArtLayers.Add().Name = "Unsaved Neotrix QA layer"
    assert not document.Saved
    def save(path):
        core.appPlugin.saveScene(core, path)
        return Path(path).is_file()
    destination = save_next(source, save)
    document.Close(2)
    document = ps.Open(str(destination))
    assert any(document.ArtLayers.Item(i).Name == "Unsaved Neotrix QA layer" for i in range(1, document.ArtLayers.Count + 1))
    (directory / "result.json").write_text(json.dumps({"application": ps.Version, "saved": destination.name,
        "unsaved_changes_preserved": True, "reopened": True}, indent=2))
    print("NEOTRIX_PHOTOSHOP_SAVE_REOPEN_PASS", destination.name)
finally:
    if document:
        document.Close(2)
    if original:
        ps.ActiveDocument = original
