"""Shared, project-relative stage labels. Never moves production documents."""
import os
import hashlib
from pathlib import Path
from .storage import atomic_json, read_json, fingerprint, exclusive_lock, user_dir

# Shot stages in template order (03_PRODUCTION/WORK/3D/SHOTS/<shot>/PROJECTS/<STAGE>).
# 'other' keeps its key so existing shared assignments remain valid; its folder is OTHERS.
STAGES = {'modelling': 'Modelling', 'rigging': 'Rigging', 'layout': 'Layout', 'animation': 'Animation',
          'fx': 'FX', 'lighting': 'Lighting', 'compositing': 'Compositing', 'other': 'Others',
          'unassigned': 'Others'}
STAGE_NOTES = {'modelling': 'Shot-specific modelling and geometry work.',
               'rigging': 'Shot-specific rigs, controls and deformation setup.',
               'layout': 'Shot cameras, composition, staging and rough timing.',
               'animation': 'Shot character, object and camera animation.',
               'fx': 'Editable shot simulation and effects setups.',
               'lighting': 'Shot lighting, materials, look development and render setup.',
               'compositing': 'Editable shot composites of renders, footage and effects.',
               'other': 'Other editable shot work that does not fit a named stage.',
               'unassigned': 'General saves kept directly in the shot PROJECTS folder.'}
# Stage folder names directly under a shot's PROJECTS folder.
STAGE_FOLDERS = {'modelling': 'modelling', 'modeling': 'modelling', 'rigging': 'rigging', 'layout': 'layout',
                 'animation': 'animation', 'fx': 'fx', 'lighting': 'lighting', 'compositing': 'compositing',
                 'others': 'other', 'other': 'other'}
ALL_STAGES = 'all'


def inferred_stage(file):
    parts = file['relative'].replace('\\', '/').lower().split('/')[:-1]
    for index, part in enumerate(parts[:-1]):
        if part == 'projects' and parts[index+1] in STAGE_FOLDERS:
            return STAGE_FOLDERS[parts[index+1]]
    if 'compositing' in parts:
        return 'compositing'
    if '3d' in parts and 'assets' in parts and 'projects' in parts:
        return 'modelling'
    if '3d' in parts and 'shots' in parts and 'projects' in parts:
        return 'other'
    aliases = {'Modeling': 'modelling', 'Rigging': 'rigging', 'Layout': 'layout', 'Animation': 'animation',
               'FX': 'fx', 'Lighting': 'lighting', 'Post': 'compositing'}
    if file.get('stage') in aliases and file.get('department') != 'Post':
        return aliases[file['stage']]
    return 'other'


def stage_folder(file):
    """The folder a file sits in, one level above it (e.g. LIGHTING), for the all-stages view."""
    parts = file['relative'].replace('\\', '/').split('/')
    return parts[-2] if len(parts) > 1 else ''


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
            if not isinstance(document, dict) or document.get('format') != 1 or not isinstance(document.get('assignments'), dict):
                raise ValueError('Unsupported stage-label document. Reload or contact your project administrator.')
            if any(not isinstance(v, str) or v not in STAGES or Path(k).is_absolute() or '..' in k.replace('\\','/').split('/')
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
        stage = document.get('assignments', {}).get(relative, inferred_stage(file))
        return 'other' if stage == 'unassigned' else stage


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
