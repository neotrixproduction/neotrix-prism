"""Build a portable distribution with explicit files and runtime licenses."""
import hashlib
import importlib.metadata
import json
import shutil
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_integrations import build

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neotrix_prism import __version__
PACKAGE = ROOT / "dist" / ("Neotrix-Prism-" + __version__ + "-Windows")


def main():
    PACKAGE.mkdir(parents=True, exist_ok=True)
    for name in ("Prism", "neotrix_prism", "runtime"):
        shutil.copytree(ROOT / name, PACKAGE / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "PythonLibs", "Python313", "Python311", "graph_ui.py", "graph.py"))
    shutil.copytree(ROOT / "docs", PACKAGE / "docs", dirs_exist_ok=True)
    shutil.copytree(ROOT / "assets", PACKAGE / "assets", dirs_exist_ok=True)
    (PACKAGE / "scripts").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "scripts/install-integrations.ps1", PACKAGE / "scripts/install-integrations.ps1")
    for name in ("launch.py", "README.md", "UPSTREAM.md", "VALIDATION.md", "requirements-neotrix.txt", "requirements-runtime-lock.txt", "license-LGPL.txt", "license_GPL.txt"):
        shutil.copy2(ROOT / name, PACKAGE / name)
    (PACKAGE / "Launch Neotrix Prism.cmd").write_text('@echo off\nstart "" "%~dp0runtime\\pythonw.exe" "%~dp0launch.py"\n')
    (PACKAGE / "Install Integrations.cmd").write_text('@echo off\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\install-integrations.ps1"\npause\n')
    build(PACKAGE / "integration-packages")
    licenses = PACKAGE / "ThirdPartyLicenses"
    licenses.mkdir(exist_ok=True)
    records = []
    for metadata in (ROOT / "runtime/Lib").glob("*.dist-info"):
        dist = importlib.metadata.PathDistribution(metadata)
        records.append({"name": dist.metadata["Name"], "version": dist.version,
                        "license": dist.metadata.get("License-Expression", dist.metadata.get("License", ""))})
        for file in metadata.rglob("*"):
            if file.is_file() and ("license" in file.name.lower() or "copying" in file.name.lower()):
                target = licenses / metadata.name / file.relative_to(metadata)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
    (licenses / "packages.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    archive = ROOT / "dist" / (PACKAGE.name + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as package:
        for file in PACKAGE.rglob("*"):
            if file.is_file():
                package.write(file, Path(PACKAGE.name) / file.relative_to(PACKAGE))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".sha256").write_text(checksum + "  " + archive.name + "\n")
    print(json.dumps({"package": str(PACKAGE), "zip": str(archive), "sha256": checksum, "bytes": archive.stat().st_size}, indent=2))


if __name__ == "__main__":
    main()
