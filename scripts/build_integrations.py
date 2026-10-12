"""Generate installation packages from reviewed panel sources."""
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(destination):
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    for app in ("photoshop", "aftereffects"):
        shutil.copytree(ROOT / "integrations" / app, target / app, dirs_exist_ok=True)
        shutil.copy2(ROOT / "integrations" / "panel.css", target / app / "panel.css")
    ae = target / "aftereffects"
    (ae / "CSXS").mkdir(exist_ok=True)
    shutil.copy2(ae / "manifest.xml", ae / "CSXS" / "manifest.xml")
    shutil.copy2(ROOT / "Prism/Plugins/Apps/AfterEffects/Integration/prism.aep/js/libs/CSInterface.js", ae / "CSInterface.js")
    with zipfile.ZipFile(target / "NeotrixPrismPhotoshop.ccx", "w", zipfile.ZIP_DEFLATED) as package:
        for file in (target / "photoshop").rglob("*"):
            if file.is_file():
                package.write(file, file.relative_to(target / "photoshop").as_posix())
    shutil.copytree(ROOT / "integrations" / "blender" / "neotrix_prism", target / "neotrix_prism_blender", dirs_exist_ok=True)


if __name__ == "__main__":
    import sys
    build(sys.argv[1])
