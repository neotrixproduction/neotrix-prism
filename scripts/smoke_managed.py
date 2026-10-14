"""Validate upstream managed-project creation and its native browser in the fork."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEOTRIX_USER_DIR"] = str(ROOT / "artifacts/managed-prefs")
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication([])
from neotrix_prism.integration import get_core
core = get_core("Standalone", no_ui=True)
directory = ROOT / "artifacts/managed-project"
config = directory / "00_Pipeline/pipeline.json"
if not config.exists():
    result = core.projects.createProject("Neotrix QA Managed", str(directory))
    assert result, "Upstream createProject failed"
core.changeProject(str(config))
from ProjectScripts.ProjectBrowser import ProjectBrowser
browser = ProjectBrowser(core=core)
browser.setWindowTitle("Neotrix Prism · Managed projects")
from neotrix_prism.design import native_theme
native_theme(browser)
browser.show()
app.processEvents()
browser.grab().save(str(ROOT / "artifacts/managed-browser.png"))
print("NEOTRIX_MANAGED_CREATE_BROWSER_PASS", core.projectName)
browser.close()
