"""Create one test AI document and verify explorer-style opening in Illustrator."""
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import win32com.client
from neotrix_prism.apps import open_file, discover
ai = win32com.client.Dispatch("Illustrator.Application")
original = None
try:
    original = ai.ActiveDocument
except Exception:
    pass
document = None
try:
    document = ai.Documents.Add(2, 128, 128)
    document.PathItems.Rectangle(110, 12, 100, 100)
    output = ROOT / "artifacts/app-smoke/Illustrator"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "Neotrix_QA_v001.ai"
    options = win32com.client.Dispatch("Illustrator.IllustratorSaveOptions")
    document.SaveAs(str(path), options)
    document.Close(2)
    document = None
    open_file(str(path), "Illustrator", discover())
    for _ in range(60):
        try:
            if str(ai.ActiveDocument.FullName).lower() == str(path).lower():
                document = ai.ActiveDocument
                break
        except Exception:
            pass
        time.sleep(.25)
    assert document, "Illustrator did not open the requested test file."
    (output / "result.json").write_text(json.dumps({"application": ai.Version, "opened": path.name,
        "document_verified": True}, indent=2))
    print("NEOTRIX_ILLUSTRATOR_OPEN_PASS")
finally:
    if document:
        document.Close(2)
    if original:
        original.Activate()
