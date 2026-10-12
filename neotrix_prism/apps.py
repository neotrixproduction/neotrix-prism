"""Application launching, using explicit argument lists and Windows associations."""
import os
import subprocess
from pathlib import Path


def discover():
    found = {}
    patterns = {"Blender": [r"C:\blender*\blender.exe", r"C:\Program Files\Blender Foundation\Blender*\blender.exe"],
                "Photoshop": [r"C:\Program Files\Adobe\Adobe Photoshop*\Photoshop.exe"],
                "Illustrator": [r"C:\Program Files\Adobe\Adobe Illustrator*\Support Files\Contents\Windows\Illustrator.exe"],
                "After Effects": [r"C:\Program Files\Adobe\Adobe After Effects*\Support Files\AfterFX.exe"],
                "Fusion": [r"C:\Program Files\Blackmagic Design\Fusion*\Fusion.exe"]}
    import glob
    for app, globs in patterns.items():
        matches = sorted({p for pattern in globs for p in glob.glob(pattern)})
        if matches:
            found[app] = matches[-1]
    return found


def open_file(path, application, configured, executable=None):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("This file is unavailable. Reconnect storage or refresh the project.")
    executable = executable or configured.get(application)
    if executable:
        if not Path(executable).is_file():
            raise FileNotFoundError("The configured application is missing. Update its executable in Settings.")
        return subprocess.Popen([str(executable), str(path)], shell=False)
    if os.name == "nt":
        try:
            os.startfile(str(path))
        except OSError:
            raise RuntimeError("No application is associated with this file. Choose Open With or configure it in Settings.")
    else:
        raise RuntimeError("Configure an executable for this application.")


def reveal(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError("This location is unavailable.")
    if os.name == "nt":
        subprocess.Popen(["explorer.exe", "/select,", str(path)], shell=False)
