"""Local preferences, atomic shared documents and activity records."""
import hashlib
import copy
import json
import math
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
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
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


@contextmanager
def preference_lock(root):
    """An OS-held lock releases even if a window crashes; no stale lockfiles."""
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/'preferences.lock').open('a+b') as handle:
        if handle.tell()==0:
            handle.write(b'0');handle.flush()
        deadline=time.monotonic()+5
        while True:
            try:
                handle.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()>deadline:
                    raise RuntimeError('Another Prism window is saving preferences. Try again shortly.')
                time.sleep(.02)
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def clean_paths(items):
    return list(dict.fromkeys(p for p in items if isinstance(p,str) and p.strip())) if isinstance(items,list) else []


class Settings:
    def __init__(self):
        self.path = user_dir() / "settings.json"
        self.favorites_path=self.path.with_name('favorites.json')
        self.backup_dir=self.path.parent/'preference-backups'
        self.recovery_notice=''
        self.data = self._read_settings()
        self._normalize(self.data)
        self.data['favorites']=self._read_favorites(self.data)
        self._baseline=copy.deepcopy(self.data)
        if not self.favorites_path.exists():
            # Establish the independent store and its first backup on launch,
            # before an unrelated preferences change can overwrite the mirror.
            self.save()

    @staticmethod
    def _normalize(data):
        defaults = {"roots": [DEFAULT_ROOT], "apps": {}, "favorites": [], "recent": [],
                    "theme": "dark", "reduced_motion": False,
                    "sound": True, "sound_hover": True, "sound_volume": 70}
        for key in ('favorites','recent'):
            data[key]=clean_paths(data.get(key,[]))
        for key, value in defaults.items():
            current=data.get(key)
            valid=isinstance(current,type(value))
            if isinstance(value,list):valid=valid and all(isinstance(p,str) and p.strip() for p in current)
            elif isinstance(value,dict):valid=valid and all(isinstance(k,str) and isinstance(v,str) for k,v in current.items())
            elif isinstance(value,int) and not isinstance(value,bool):valid=valid and not isinstance(current,bool) and 0<=current<=100
            if not valid:data[key]=copy.deepcopy(value)
        data['theme']='dark'

    def _read_settings(self):
        try:
            data=json.loads(self.path.read_text(encoding='utf-8-sig'))
            if not isinstance(data,dict):raise ValueError('Invalid preferences')
            return data
        except FileNotFoundError:return {}
        except (OSError,ValueError):
            for backup in sorted(self.backup_dir.glob('settings-*.json'),reverse=True):
                data=read_json(backup)
                if isinstance(data,dict):
                    self.recovery_notice='Preferences recovered from an automatic backup.'
                    return data
            self.recovery_notice='Preferences are damaged; the original is preserved. Favorites use their separate store.'
            return {}

    def _read_favorites(self,settings):
        if not self.favorites_path.exists():return clean_paths(settings.get('favorites',[]))
        data=read_json(self.favorites_path)
        if isinstance(data,dict) and data.get('format')==1 and isinstance(data.get('items'),list):
            return clean_paths(data['items'])
        for backup in sorted(self.backup_dir.glob('favorites-*.json'),reverse=True):
            data=read_json(backup)
            if isinstance(data,dict) and data.get('format')==1 and isinstance(data.get('items'),list):
                self.recovery_notice='Favorites recovered from an automatic backup.'
                return clean_paths(data['items'])
        self.recovery_notice='Favorites store is damaged; showing the last preference copy and preserving the original.'
        return clean_paths(settings.get('favorites',[]))

    def _snapshot(self,prefix,data,keep):
        self.backup_dir.mkdir(parents=True,exist_ok=True)
        target=self.backup_dir/(prefix+'-'+str(time.time_ns())+'.json')
        atomic_json(target,data)
        for old in sorted(self.backup_dir.glob(prefix+'-*.json'),reverse=True)[keep:]:old.unlink(missing_ok=True)

    def _merge(self,latest):
        result=copy.deepcopy(latest)
        for key,value in self.data.items():
            if key!='favorites' and value!=self._baseline.get(key):result[key]=copy.deepcopy(value)
        old=clean_paths(self._baseline.get('favorites',[]))
        current=clean_paths(self.data['favorites']) if isinstance(self.data.get('favorites'),list) else old
        removed=set(old)-set(current)
        result['favorites']=[p for p in latest.get('favorites',[]) if p not in removed]
        result['favorites']+= [p for p in current if p not in old and p not in result['favorites']]
        return result

    def reload(self):
        latest=self._read_settings();self._normalize(latest)
        latest['favorites']=self._read_favorites(latest)
        merged=self._merge(latest)
        self._baseline=copy.deepcopy(latest)
        self.data=merged

    def save(self):
        with preference_lock(self.path.parent):
            latest=self._read_settings();self._normalize(latest)
            favorites=self._read_favorites(latest)
            latest['favorites']=favorites
            result=self._merge(latest)
            raw=read_json(self.path)
            if self.path.exists() and not isinstance(raw,dict):
                # Never discard the bytes of an unreadable file while repairing it.
                self.backup_dir.mkdir(parents=True,exist_ok=True)
                (self.backup_dir/('corrupt-settings-'+str(time.time_ns())+'.raw')).write_bytes(self.path.read_bytes())
            if isinstance(raw,dict) and raw!=result:self._snapshot('settings',raw,20)
            existing=read_json(self.favorites_path)
            if self.favorites_path.exists() and not (isinstance(existing,dict) and existing.get('format')==1 and isinstance(existing.get('items'),list)):
                self.backup_dir.mkdir(parents=True,exist_ok=True)
                (self.backup_dir/('corrupt-favorites-'+str(time.time_ns())+'.raw')).write_bytes(self.favorites_path.read_bytes())
            if not self.favorites_path.exists() or favorites!=result['favorites']:
                self._snapshot('favorites',{'format':1,'items':favorites},50)
                if favorites!=result['favorites']:
                    self._snapshot('favorites',{'format':1,'items':result['favorites']},50)
            # This independent file is authoritative; legacy preference writers
            # cannot erase it by saving an older settings.json snapshot.
            atomic_json(self.favorites_path,{'format':1,'items':result['favorites']})
            atomic_json(self.path,result)
            self.data=result
            self._baseline=copy.deepcopy(result)

    def favorite_backups(self):
        result=[]
        for path in sorted(self.backup_dir.glob('favorites-*.json'),reverse=True):
            data=read_json(path)
            if isinstance(data,dict) and data.get('format')==1 and isinstance(data.get('items'),list):
                result.append((path,clean_paths(data['items'])))
        return result

    def restore_favorites(self,backup):
        candidates=dict(self.favorite_backups())
        if Path(backup) not in candidates:raise ValueError('Choose an available favorites backup.')
        self.reload()
        self.data['favorites']=list(dict.fromkeys(self.data['favorites']+candidates[Path(backup)]))
        self.save()

    def favorite(self, path):
        favorites = self.data["favorites"]
        if path in favorites:favorites.remove(path)
        else:favorites.append(path)
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
            record = json.loads(line)
            if not isinstance(record, dict) or not isinstance(record.get('event'), str):
                continue
            timestamp = record.get('time')
            if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not math.isfinite(timestamp):
                continue
            time.localtime(timestamp)
            if any(key in record and not isinstance(record[key], str) for key in ('path','name','application','stage')):
                continue
            records.append(record)
        except (ValueError, OverflowError, OSError):
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
