"""Shared, project-relative stage labels. Never moves production documents."""
import os
import hashlib
from pathlib import Path
from .storage import atomic_json, read_json, fingerprint, exclusive_lock, user_dir

STAGES = {'modelling': 'Modelling', 'layout': 'Layout', 'lighting': 'Lighting',
          'compositing': 'Compositing', 'other': 'Other work', 'unassigned': 'Unassigned'}


def inferred_stage(file):
    parts = file['relative'].replace('\\', '/').lower().split('/')[:-1]
    if 'compositing' in parts:
        return 'compositing'
    if '3d' in parts and 'assets' in parts and 'projects' in parts:
        return 'modelling'
    if '3d' in parts and 'shots' in parts and 'projects' in parts:
        return 'unassigned'
    aliases = {'Modeling': 'modelling', 'Layout': 'layout', 'Lighting': 'lighting', 'Post': 'compositing'}
    if file.get('stage') in aliases and file.get('department') != 'Post':
        return aliases[file['stage']]
    return 'unassigned' if file.get('stage') == 'Unspecified' and file.get('department') == '3D' else 'other'


class StageStore:
    def __init__(self, project):
        self.project = Path(project)
        self.path = self.project / '_TOOLS/neotrix-prism/stages.json'
        self.cache = user_dir() / 'stages' / (hashlib.sha256(os.path.normcase(str(project)).encode()).hexdigest()+'.json')

    def relative(self, path):
        return Path(path).resolve().relative_to(self.project.resolve()).as_posix()

    def load(self, shared=True):
        if not shared:
            return {**read_json(self.cache, {'format': 1, 'assignments': {}, 'fingerprint': None}), 'writable': False}
        try:
            # Read bytes and fingerprint the same snapshot, avoiding a concurrent-read race.
            import json
            try:
                data = self.path.read_bytes()
            except FileNotFoundError:
                if not self.project.is_dir():
                    raise OSError('Project storage is unavailable.')
                data = None
            document = json.loads(data) if data is not None else {'format': 1, 'assignments': {}}
            if document.get('format') != 1 or not isinstance(document.get('assignments'), dict):
                raise ValueError('Unsupported stage-label document. Reload or contact your project administrator.')
            if any(v not in STAGES or Path(k).is_absolute() or '..' in k.replace('\\','/').split('/')
                   for k,v in document['assignments'].items()):
                raise ValueError('Invalid project-relative stage assignment.')
            check = self.path if self.path.exists() else self.project
            result = {**document, 'fingerprint': hashlib.sha256(data).hexdigest() if data is not None else None,
                      'writable': os.access(check, os.W_OK), 'notice': ''}
            atomic_json(self.cache, result)
            return result
        except OSError as exc:
            cached = self.load(False)
            return {**cached, 'writable': False, 'notice': str(exc)}

    def save(self, paths, stage, expected):
        if stage not in STAGES:
            raise ValueError('Choose a supported stage.')
        if not self.project.is_dir():
            raise OSError('Reconnect project storage before assigning stages.')
        relatives = [self.relative(path) for path in paths]
        with exclusive_lock(self.path.with_suffix('.lock')):
            if fingerprint(self.path) != expected:
                raise RuntimeError('Stage labels changed on another workstation. Refresh the project before assigning again.')
            document = self.load()
            if not document['writable']:
                raise PermissionError('Project stage labels are read-only. Ask for write access to _TOOLS.')
            assignments = dict(document['assignments'])
            assignments.update(dict.fromkeys(relatives, stage))
            atomic_json(self.path, {'format': 1, 'assignments': assignments})
        return self.load()

    def stage(self, file, document):
        relative = file['relative'].replace('\\','/')
        return document.get('assignments', {}).get(relative, inferred_stage(file))


def inheritance_snapshot(source, project=None):
    candidates = ([Path(project)] if project else []) + list(Path(source).parents)
    for root in candidates:
        store = StageStore(root)
        if store.path.is_file():
            document = store.load()
            try:
                relative = store.relative(source)
            except ValueError:
                continue
            stage = document['assignments'].get(relative)
            return (store, document['fingerprint'], stage) if stage else None
    return None
