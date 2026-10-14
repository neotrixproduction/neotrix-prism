"""Cooperative cross-workstation version reservations and application saves."""
import os
import re
from pathlib import Path
from .storage import exclusive_lock, activity

TOKEN = re.compile(r"(?i)(?<![a-z0-9])(v)(\d+)(?!\d)")


def next_version(source):
    source = Path(source)
    matches = list(TOKEN.finditer(source.stem))
    if matches:
        token = matches[-1]
        prefix, suffix = source.stem[:token.start()], source.stem[token.end():]
        letter, width, highest = token[1], len(token[2]), int(token[2])
    else:
        prefix, suffix, letter, width, highest = source.stem + "_", "", "v", 3, 0
    pattern = re.compile(re.escape(prefix) + r"v(\d+)" + re.escape(suffix) + re.escape(source.suffix) + r"$", re.I)
    for entry in source.parent.iterdir():
        match = pattern.fullmatch(entry.name)
        if match:
            highest = max(highest, int(match[1]))
    return source.with_name(prefix + letter + str(highest + 1).zfill(width) + suffix + source.suffix)


def save_next(source, save_callback, expected=None):
    """Callback saves the CURRENT in-memory document, not a copied disk file."""
    source = Path(source)
    with exclusive_lock(source.parent / ".neotrix-version.lock"):
        destination = next_version(source)
        if expected is not None and os.path.normcase(str(destination)) != os.path.normcase(str(expected)):
            raise RuntimeError("Another version was saved after the preview. Review the new filename and try again.")
        if destination.exists():
            raise FileExistsError(str(destination))
        result = save_callback(str(destination))
        if result is False or result is None or not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("The application did not complete the save. Check its messages before retrying.")
        activity("New version saved", path=str(destination))
        return destination
