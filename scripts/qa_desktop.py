"""Full native-widget captures at selected Windows scale and theme."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEOTRIX_USER_DIR"] = str(ROOT / "artifacts/visual-prefs" / os.environ.get("QT_SCALE_FACTOR", "default"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from neotrix_prism.ui import MainWindow
from neotrix_prism.storage import Settings, atomic_json
from neotrix_prism.capture import capture
from neotrix_prism.design import icon
root = ROOT / "artifacts/visual-library"
project = root / "Neotrix Studio Film"
files = ["03_PRODUCTION/WORK/3D/SHOTS/NTX_Landscape_0010/PROJECTS/NTX_Landscape_0010_v001.blend",
         "03_PRODUCTION/WORK/3D/SHOTS/NTX_Landscape_0010/PROJECTS/NTX_Landscape_0010_v002.blend",
         "03_PRODUCTION/WORK/GRAPHIC_DESIGN/PROJECTS/Brand_Poster_v003.psd",
         "03_PRODUCTION/WORK/GRAPHIC_DESIGN/PROJECTS/Neotrix_Logotype_v002.ai",
         "03_PRODUCTION/WORK/MOTION_GRAPHICS/PROJECTS/Title_Sequence_V0004.aep",
         "04_POST/PROJECTS/NTX_0010_v002.comp", "05_DELIVERY/Review_v002.mp4"]
for relative in files:
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(b"Neotrix UI indexing fixture. Do not open as a creative document.")
for name in ("Neotrix Brand System", "Neotrix Motion Library", "Neotrix Product Launch",
             "Neotrix Character Lab","Neotrix Design Library","Neotrix Studio Series","Neotrix Title Design"):
    (root / name).mkdir(parents=True, exist_ok=True)
app = QApplication([])
settings = Settings()
settings.data.update(roots=[str(root)], graph_root=str(root), reduced_motion=True, theme=sys.argv[1] if len(sys.argv)>1 else "light",
                     favorites=[str(project)], recent=[str(project)])
window = MainWindow(settings)
if os.environ.get("NEOTRIX_MINIMUM_SIZE"):
    window.resize(1024, 720)
window.show()
directory = ROOT / "artifacts/screenshots" / (settings.data["theme"] + "-" + os.environ.get("NEOTRIX_CAPTURE_NAME", os.environ.get("QT_SCALE_FACTOR", "default")))
QTimer.singleShot(800, lambda: capture(window, directory, app))
app.exec()
