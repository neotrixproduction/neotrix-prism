"""Confirm managed version saves still use Prism's native metadata workflow."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "runtime/Lib"))
os.environ["NEOTRIX_USER_DIR"] = str(ROOT / "artifacts/blender-managed-prefs")
from PySide6.QtWidgets import QApplication
app = QApplication([])
import bpy
from neotrix_prism.integration import get_core
core = get_core("Blender", no_ui=True)
project = ROOT / "artifacts/blender-managed-project"
config = project / "00_Pipeline/pipeline.json"
if not config.exists():
    assert core.projects.createProject("Neotrix Blender QA", str(project))
core.changeProject(str(config))
entity = {"type": "asset", "asset_path": "NeotrixQA"}
core.entities.createAsset(entity)
core.entities.createDepartment("mod", entity)
core.entities.createCategory(entity, "mod", "main")
source = core.generateScenePath(entity, department="mod", task="main", extension=".blend", version="v0001")
Path(source).parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=source)
assert core.fileInPipeline(source), source
bpy.data.objects["Cube"].location.y = 8.5
destination = core.saveScene(comment="qa", versionUp=True, location="global")
assert destination and Path(destination).is_file(), destination
bpy.ops.wm.open_mainfile(filepath=destination)
assert bpy.data.objects["Cube"].location.y == 8.5
print("NEOTRIX_NATIVE_MANAGED_VERSION_PASS", Path(destination).name)
