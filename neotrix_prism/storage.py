"""Local preferences, atomic shared documents and activity records."""
import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_ROOT = r"\\NeoVault\Relay"


def user_dir():
    root = Path(os.environ.get("NEOTRIX_USER_DIR", Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NeotrixPrism"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".neotrix-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fingerprint(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


@contextmanager
def exclusive_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        raise RuntimeError("This item is being edited or saved by another session. Try again after it finishes.")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"pid": os.getpid(), "created": time.time(), "machine": os.environ.get("COMPUTERNAME", "")}, stream)
        yield
    finally:
        path.unlink(missing_ok=True)


class Settings:
    def __init__(self):
        self.path = user_dir() / "settings.json"
        self.data = read_json(self.path, {})
        for key, value in {"roots": [DEFAULT_ROOT], "graph_root": DEFAULT_ROOT, "apps": {}, "favorites": [], "recent": [],
                           "theme": "light", "reduced_motion": False}.items():
            self.data.setdefault(key, value)

    def save(self):
        atomic_json(self.path, self.data)

    def favorite(self, path):
        favorites = self.data["favorites"]
        if path in favorites:
            favorites.remove(path)
        else:
            favorites.append(path)
        self.save()

    def recent(self, path):
        self.data["recent"] = [path] + [p for p in self.data["recent"] if p != path][:11]
        self.save()


def activity(event, **details):
    record = {"time": time.time(), "event": event, **details}
    with (user_dir() / "activity.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def history():
    path = user_dir() / "activity.jsonl"
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines()[-250:]:
        try:
            records.append(json.loads(line))
        except ValueError:
            pass
    return list(reversed(records))


class GraphLibrary:
    def __init__(self, root):
        self.path = Path(root) / "_NEOTRIX_PRISM" / "Graphs"
        self.root = Path(root)
        self.cache = user_dir() / ("graphs-" + hashlib.sha256(str(root).encode()).hexdigest()[:12] + ".json")

    def online(self):
        return self.root.is_dir()

    def list(self):
        if not self.online():
            return read_json(self.cache, [])
        records = []
        if self.path.exists():
            for path in sorted(self.path.glob("*.json")):
                graph = read_json(path)
                if isinstance(graph, dict) and graph.get("format") == 1:
                    records.append({"filename": path.name, "graph": graph, "fingerprint": fingerprint(path)})
        atomic_json(self.cache, records)
        return records

    def save(self, filename, graph, expected=None):
        if not self.online():
            raise OSError("Relay is disconnected. Reconnect before saving workflows.")
        filename = Path(filename).name
        if not filename.endswith(".json") or filename in (".json", ""):
            raise ValueError("A workflow filename ending in .json is required.")
        path = self.path / filename
        with exclusive_lock(path.with_suffix(".lock")):
            if fingerprint(path) != expected:
                raise RuntimeError("This workflow changed since you opened it. Reload it or save under a new name.")
            atomic_json(path, graph)
        self.list()
        activity("Workflow saved", name=graph.get("name", filename))
        return fingerprint(path)
