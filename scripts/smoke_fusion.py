"""Launch a valid minimal composition, then inspect the actual Fusion window."""
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neotrix_prism.apps import open_file, discover
directory = ROOT / "artifacts/app-smoke/Fusion"
directory.mkdir(parents=True, exist_ok=True)
path = directory / "Neotrix_QA_v001.comp"
path.write_text('Composition { CurrentTime = 0, RenderRange = { 0, 24 }, GlobalRange = { 0, 24 }, Tools = {} }\n')
process = open_file(str(path), "Fusion", discover())
print("Fusion requested:", process.pid)
import win32gui
for _ in range(120):
    titles = []
    win32gui.EnumWindows(lambda h, _: titles.append(win32gui.GetWindowText(h)) if win32gui.IsWindowVisible(h) else None, None)
    if any("Neotrix_QA_v001.comp" in title for title in titles):
        (directory / "result.json").write_text(json.dumps({"application": "Fusion 21", "opened": path.name,
                                                         "window_verified": True}, indent=2))
        print("NEOTRIX_FUSION_OPEN_PASS")
        break
    time.sleep(.5)
else:
    raise RuntimeError("Fusion did not show the requested composition within 60 seconds.")
