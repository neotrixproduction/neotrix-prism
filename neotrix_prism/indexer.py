"""Filesystem-only indexing; no creative application imports or writes."""
import hashlib
import os
import re
import time
from pathlib import Path
from .storage import atomic_json, read_json, user_dir

EXTENSIONS = {".blend": "Blender", ".ai": "Illustrator", ".psd": "Photoshop",
              ".psb": "Photoshop", ".aep": "After Effects", ".aepx": "After Effects", ".comp": "Fusion"}
MEDIA = {".png": "Image", ".jpg": "Image", ".jpeg": "Image", ".exr": "Image", ".tif": "Image", ".tiff": "Image",
         ".mp4": "Video", ".mov": "Video", ".mkv": "Video", ".wav": "Audio", ".mp3": "Audio"}
OUTPUT_DIRS = {"exports", "export", "renders", "render", "playblasts", "05_delivery", "delivery"}
SKIP = {"node_modules", "__pycache__", "$recycle.bin", "#recycle", "system volume information",
        "_shot_template", "_neotrix_prism", "auto-save", "autosave", "adobe after effects auto-save",
        ".git", "synologydrive", "@eadir", "_tools"}
STAGES = {"Preproduction": ("preproduction", "preprod", "storyboard", "animatic"),
          "Modeling": ("modeling", "modelling", "model"), "Lookdev": ("lookdev", "shading", "texture"),
          "Rigging": ("rigging", "rig"), "Layout": ("layout", "blocking"), "Animation": ("animation", "anim"),
          "Lighting": ("lighting", "light"), "Rendering": ("rendering", "renders", "render"),
          "Post": ("post", "compositing", "comp", "finishing"), "Delivery": ("delivery", "final", "approved")}
DEPARTMENTS = {"3D": "3D", "GRAPHIC_DESIGN": "Graphic Design", "MOTION_GRAPHICS": "Motion Graphics",
               "AI_GENERATION": "AI Generation", "04_POST": "Post", "02_PREPRODUCTION": "Preproduction"}


def natural(text):
    return tuple((1, int(p)) if p.isdigit() else (0, p.lower()) for p in re.split(r"(\d+)", text))


def skip_dir(name):
    return name.lower() in SKIP or name.startswith((".", "#", "@")) or name.lower().endswith(".blend.neotrix")


def list_projects(root):
    return sorted([str(p) for p in Path(root).iterdir() if p.is_dir() and not p.is_symlink() and not skip_dir(p.name)], key=natural)


def parse(path, project):
    path, project = Path(path), Path(project)
    relative = path.relative_to(project)
    parts = relative.parts
    stage, department, shot, variant, version = "Unspecified", "Unspecified", "Unspecified", "Unspecified", "Unversioned"
    for part in parts[:-1]:
        if part.upper() in DEPARTMENTS:
            department = DEPARTMENTS[part.upper()]
        words = re.split(r"[^a-z0-9]+", part.lower())
        for label, aliases in STAGES.items():
            if any(a in words for a in aliases):
                stage = label
    for part in reversed(parts):
        match = re.search(r"(?i)(?:^|[^a-z0-9])(?:shot|sh|sc)[ _-]*(\d+)(?:[^0-9]|$)", part)
        if match:
            shot = "Shot " + match[1].zfill(3)
            break
    if shot == "Unspecified":
        match = re.match(r"(?i)^[a-z][a-z0-9]*(?:[ _-]+[a-z][a-z0-9]*)*[ _-]+(\d{3,5})(?:[ _-]|$)", path.stem)
        if match:
            shot = "Shot " + match[1].zfill(3)
    for part in reversed(parts):
        match = re.search(r"(?i)(?:^|[^a-z0-9])v(?:er(?:sion)?)?[ _-]*(\d+)(?:[^0-9]|$)", part)
        if match:
            version = "v" + match[1].zfill(3)
            break
    for i, part in enumerate(parts[:-1]):
        if part.lower() == "shots" and i + 1 < len(parts) - 1:
            candidate = parts[i + 1]
            match = re.match(r"(?i)^[a-z0-9]+_(.+)_\d+$", candidate)
            if match:
                variant = match[1]
            elif not re.search(r"(?i)(?:shot|sh|sc)[ _-]*\d|^[a-z0-9]+_\d+$", candidate):
                variant = candidate
            break
    stat = path.stat()
    if variant == 'Unspecified':
        match = re.match(r'(?i)^[a-z]{3}_([a-z][a-z0-9]*)_(?:\d{4}_)?v\d+(?:_|$)', path.stem)
        if match:
            variant = match[1]
    preview = None
    for suffix in (".png", ".jpg", ".jpeg"):
        candidate = path.with_suffix(suffix)
        if candidate.exists() and candidate.stat().st_size < 10 * 1024 * 1024:
            preview = str(candidate)
            break
    return {"path": str(path), "relative": str(relative), "name": path.name, "project": project.name,
            "application": EXTENSIONS.get(path.suffix.lower(), MEDIA.get(path.suffix.lower(), "File")), "department": department, "variant": variant,
            "kind": "output" if path.suffix.lower() in MEDIA or any(p.lower() in OUTPUT_DIRS for p in parts[:-1]) else "working",
            "shot": shot, "stage": stage, "version": version, "size": stat.st_size,
            "modified": stat.st_mtime, "preview": preview}


def cache_path(project):
    return user_dir() / "cache" / (hashlib.sha256(os.path.normcase(str(project)).encode()).hexdigest() + ".json")


def cached(project):
    return read_json(cache_path(project), {"project": str(project), "files": [], "errors": [], "cached": True})


def scan(project, cancel=None, progress=None):
    project = Path(project)
    if not project.is_dir():
        result = cached(project)
        result["cached"] = True
        result["errors"] = ["Project storage is unavailable. Showing the last cached index."]
        return result
    files, errors = [], []
    def error(exc):
        errors.append(str(exc))
    for directory, dirs, names in os.walk(project, followlinks=False, onerror=error):
        if cancel and cancel.is_set():
            return {"project": str(project), "files": files, "errors": errors, "cancelled": True}
        dirs[:] = [d for d in dirs if not skip_dir(d) and not Path(directory, d).is_symlink()
                   and not os.path.isjunction(Path(directory, d))] if hasattr(os.path, "isjunction") else [
                       d for d in dirs if not skip_dir(d) and not Path(directory, d).is_symlink()]
        for name in names:
            path = Path(directory, name)
            if path.is_symlink() or (path.suffix.lower() not in EXTENSIONS
               and not (path.suffix.lower() in MEDIA and any(p.lower() in OUTPUT_DIRS for p in path.relative_to(project).parts[:-1]))):
                continue
            if re.search(r"(?i)auto[- ]?save|(?:^|[_. -])(?:tmp|temp|backup)(?:[_. -]|$)", name):
                continue
            try:
                files.append(parse(path, project))
            except OSError as exc:
                error(exc)
        if progress:
            progress(len(files), str(Path(directory).relative_to(project)))
    files.sort(key=lambda f: (natural(f["relative"]), f["modified"]))
    result = {"project": str(project), "files": files, "errors": errors, "cached": False, "scanned": time.time()}
    atomic_json(cache_path(project), result)
    return result
