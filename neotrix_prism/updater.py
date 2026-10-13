"""Public Neotrix releases only; download first, replace offline with rollback."""
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path, PurePosixPath
from .storage import atomic_json, user_dir

REPOSITORY = 'neotrixproduction/neotrix-prism'
API = 'https://api.github.com/repos/' + REPOSITORY + '/releases?per_page=50'
PRODUCT = 'Neotrix.Prism'


def version_key(text):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?', text)
    if not match:
        raise ValueError('Unrecognized release version.')
    # A final release outranks a preview with the same numeric version.
    return tuple(int(n) for n in match.groups()[:3]) + (not bool(match[4]), match[4] or '')


def release_url(url):
    prefix = 'https://github.com/' + REPOSITORY + '/releases/'
    if not isinstance(url, str) or not url.startswith(prefix) or '\\' in url:
        raise ValueError('Unexpected release download source.')
    return url


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': 'Neotrix-Prism-Updater', 'Accept': 'application/vnd.github+json'}), timeout=30)


def latest_release(current, releases=None):
    if releases is None:
        with request(API) as response:
            releases = json.loads(response.read(2*1024*1024))
    if not isinstance(releases, list):
        raise ValueError('GitHub returned an invalid release list.')
    candidates = []
    for release in releases:
        if release.get('draft'):
            continue
        tag = release.get('tag_name', '')
        try:
            key = version_key(tag)
        except ValueError:
            continue
        if key <= version_key(current):
            continue
        numeric = '.'.join(str(n) for n in key[:3])
        name = 'Neotrix-Prism-' + numeric + '-Windows.zip'
        assets = {a['name']: a for a in release.get('assets', [])}
        archive = assets.get(name)
        checksum = assets.get(name[:-4]+'.sha256')
        if not archive or not checksum:
            continue
        candidates.append((key, {'tag':tag, 'version':numeric, 'name':name,
            'url':release_url(archive['browser_download_url']),
            'checksum_url':release_url(checksum['browser_download_url']),
            'size':archive.get('size',0), 'notes':release.get('body',''),
            'page':release_url(release['html_url'])}))
    return max(candidates, key=lambda c:c[0])[1] if candidates else None


def portable_root(root):
    root = Path(root).resolve()
    if (root/'.git').exists():
        return False
    try:
        manifest = json.loads((root/'portable.json').read_text(encoding='utf-8'))
        return manifest['product']==PRODUCT and manifest['platform']=='windows-x64'
    except (OSError, ValueError, KeyError, TypeError):
        return False


def prepare(release, root, cancel=None, progress=None):
    """Stage beside the installation so directory swaps stay on one volume."""
    root = Path(root).resolve()
    if not portable_root(root):
        raise ValueError('In-app installation requires an extracted portable package, not a development checkout.')
    stage = Path(tempfile.mkdtemp(prefix='.neotrix-update-', dir=root.parent))
    def check_cancel():
        if cancel is not None and cancel.is_set():
            raise InterruptedError('Update download cancelled; the installed app is unchanged.')
    try:
        check_cancel()
        with request(release_url(release['checksum_url'])) as response:
            checksum = response.read(8192).decode('utf-8-sig')
        match = re.fullmatch(r'\s*([a-fA-F0-9]{64})\s+\*?'+re.escape(release['name'])+r'\s*', checksum)
        if not match:
            raise ValueError('Missing or invalid release checksum.')
        archive = stage/'download.zip'
        digest = hashlib.sha256()
        count = 0
        with request(release_url(release['url'])) as response, archive.open('xb') as output:
            while True:
                check_cancel()
                chunk = response.read(1024*1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > 2*1024**3:
                    raise ValueError('Release archive exceeds the supported size.')
                digest.update(chunk)
                output.write(chunk)
                if progress:
                    progress(count, release.get('size',0))
        if release.get('size') and count != release['size']:
            raise ValueError('Release download is incomplete.')
        if digest.hexdigest().lower() != match[1].lower():
            raise ValueError('Release checksum mismatch. The installed app is unchanged.')
        payload = extract_package(archive, stage/'payload', release['version'], check_cancel)
        archive.unlink()
        return {'stage':str(stage), 'payload':str(payload), 'root':str(root), 'version':release['version']}
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def extract_package(archive, destination, version, check_cancel=lambda:None):
    import zipfile
    destination = Path(destination)
    expected = 'Neotrix-Prism-' + version + '-Windows'
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        if sum(e.file_size for e in entries) > 8*1024**3:
            raise ValueError('Expanded release exceeds the supported size.')
        seen = set()
        for entry in entries:
            check_cancel()
            raw = entry.orig_filename
            path = PurePosixPath(raw)
            if ('\\' in raw or ':' in raw or path.is_absolute() or '..' in path.parts
                or not path.parts or path.parts[0]!=expected
                or stat.S_ISLNK(entry.external_attr >> 16)
                or any(part.endswith((' ','.')) or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',part) for part in path.parts)):
                raise ValueError('Unsafe release archive path.')
            key = str(path).casefold()
            if key in seen:
                raise ValueError('Duplicate release archive path.')
            seen.add(key)
            target = destination.joinpath(*path.parts)
            if entry.is_dir():
                target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with package.open(entry) as source, target.open('xb') as output:
                    shutil.copyfileobj(source,output)
    payload = destination/expected
    if not portable_root(payload):
        raise ValueError('Release is not a compatible Neotrix portable package.')
    manifest=json.loads((payload/'portable.json').read_text(encoding='utf-8'))
    if manifest.get('version')!=version:
        raise ValueError('Release version does not match the package.')
    for required in ('Neotrix Prism.exe','launch.py','runtime/pythonw.exe','runtime/python.exe'):
        if not (payload/required).is_file():
            raise ValueError('Release package is missing '+required)
    return payload


def apply_on_exit(prepared, restart=True):
    """The helper runs from user storage, outside the folder being replaced."""
    root = Path(prepared['root']).resolve()
    if not portable_root(root) or not Path(prepared['payload']).is_dir():
        raise ValueError('Prepared update is no longer available.')
    helper = user_dir()/'updates'/('job-'+str(time.time_ns()))
    helper.mkdir(parents=True)
    shutil.copy2(root/'scripts/apply-update.ps1',helper/'apply-update.ps1')
    pids=[os.getpid()]
    launcher=os.environ.get('NEOTRIX_LAUNCHER_PID','')
    if launcher.isdigit():
        pids.append(int(launcher))
    job={**prepared, 'backup':str(root.parent/(root.name+'.previous-'+str(time.time_ns()))),
         'wait_pids':pids, 'restart':bool(restart), 'status':str(helper/'result.json')}
    atomic_json(helper/'job.json',job)
    subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass',
                      '-WindowStyle','Hidden','-File',str(helper/'apply-update.ps1'),'-Job',str(helper/'job.json')],
                     cwd=str(helper),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return helper/'result.json'
