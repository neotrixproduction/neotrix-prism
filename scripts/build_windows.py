"""Build a portable distribution with explicit files and runtime licenses."""
import hashlib
import importlib.metadata
import json
import shutil
import sys
import os
import subprocess
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
    for name in ('create-shortcut.ps1','functional_runtime_smoke.py','windows_launcher.cs','apply-update.ps1'):
        shutil.copy2(ROOT/'scripts'/name,PACKAGE/'scripts'/name)
    (PACKAGE/'portable.json').write_text(json.dumps({'product':'Neotrix.Prism','platform':'windows-x64',
                                                   'version':__version__}),encoding='utf-8')
    compiler = Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:x64',
                    '/reference:System.Windows.Forms.dll',
                    '/win32icon:'+str(ROOT/'assets/neotrix.ico'),
                    '/out:'+str(PACKAGE/'Neotrix Prism.exe'),str(ROOT/'scripts/windows_launcher.cs')],check=True)
    for name in ("launch.py", "START_HERE.md", "README.md", "UPSTREAM.md", "VALIDATION.md", "requirements-neotrix.txt", "requirements-runtime-lock.txt", "license-LGPL.txt", "license_GPL.txt"):
        shutil.copy2(ROOT / name, PACKAGE / name)
    (PACKAGE / "Launch Neotrix Prism.cmd").write_text('@echo off\nstart "" "%~dp0Neotrix Prism.exe"\n')
    (PACKAGE / "Create Desktop Shortcut.cmd").write_text('@echo off\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\create-shortcut.ps1"\npause\n')
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
            if file.is_file() and '__pycache__' not in file.parts and file.suffix.lower() != '.pyc':
                package.write(file, Path(PACKAGE.name) / file.relative_to(PACKAGE))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".sha256").write_text(checksum + "  " + archive.name + "\n")
    print(json.dumps({"package": str(PACKAGE), "zip": str(archive), "sha256": checksum, "bytes": archive.stat().st_size}, indent=2))


if __name__ == "__main__":
    main()
