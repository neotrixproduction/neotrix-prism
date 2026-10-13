import hashlib
import io
import json
import os
import subprocess
import threading
import zipfile
from pathlib import Path
import pytest
from neotrix_prism import updater


def release(version='0.7.0',draft=False):
    prefix='https://github.com/neotrixproduction/neotrix-prism/releases/'
    name=f'Neotrix-Prism-{version}-Windows.zip'
    return {'tag_name':'v'+version+'-preview','draft':draft,'html_url':prefix+'tag/v'+version+'-preview',
        'assets':[{'name':n,'browser_download_url':prefix+'download/v'+version+'-preview/'+n}
                  for n in (name,name[:-4]+'.sha256')]}


def package(tmp_path,version='0.7.0',extra=None):
    path=tmp_path/'package.zip'
    prefix=f'Neotrix-Prism-{version}-Windows/'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr(prefix+'portable.json',json.dumps({'product':updater.PRODUCT,'platform':'windows-x64','version':version}))
        for name in ('Neotrix Prism.exe','launch.py','runtime/pythonw.exe','runtime/python.exe'):
            z.writestr(prefix+name,b'fixture')
        if extra:z.writestr(extra,b'unsafe')
    return path


def test_release_selection_includes_preview_but_skips_draft_and_missing_assets():
    missing=release('0.9.0');missing['assets']=[]
    chosen=updater.latest_release('0.6.0',[release('0.5.0'),release('0.8.0',True),missing,release()])
    assert chosen['version']=='0.7.0'
    assert updater.latest_release('0.7.0',[release()]) is None
    with pytest.raises(ValueError):updater.release_url('https://github.com/PrismPipeline/Prism/releases/download/x/a.zip')


@pytest.mark.parametrize('extra',['../outside.txt','Neotrix-Prism-0.7.0-Windows/../../outside.txt',
    'Neotrix-Prism-0.7.0-Windows/runtime/NUL.txt','Neotrix-Prism-0.7.0-Windows/a\\b.txt'])
def test_archive_rejects_unsafe_paths(tmp_path,extra):
    archive = package(tmp_path,extra=extra)
    # Windows ZipInfo normalizes backslashes when writing, so emulate a foreign
    # ZIP writer in both filename headers to exercise the rejected raw path.
    if '\\' in extra:
        archive.write_bytes(archive.read_bytes().replace(b'a/b.txt',b'a\\b.txt'))
    with pytest.raises(ValueError,match='Unsafe'):
        updater.extract_package(archive,tmp_path/'unpacked','0.7.0')
    assert not (tmp_path/'outside.txt').exists()


def test_download_checksum_cancellation_and_preservation(tmp_path,monkeypatch):
    root=tmp_path/'installed';root.mkdir()
    (root/'portable.json').write_text(json.dumps({'product':updater.PRODUCT,'platform':'windows-x64','version':'0.6.0'}))
    (root/'keep.txt').write_text('old app')
    archive=package(tmp_path).read_bytes()
    selected=updater.latest_release('0.6.0',[release()])
    selected['size']=len(archive)
    checksum=hashlib.sha256(archive).hexdigest()+'  '+selected['name']+'\n'
    monkeypatch.setattr(updater,'request',lambda url:io.BytesIO(checksum.encode() if url.endswith('.sha256') else archive))
    staged=updater.prepare(selected,root)
    assert Path(staged['payload']).is_dir()
    assert (root/'keep.txt').read_text()=='old app'
    monkeypatch.setattr(updater,'request',lambda url:io.BytesIO(('0'*64+'  '+selected['name']).encode() if url.endswith('.sha256') else archive))
    with pytest.raises(ValueError,match='checksum mismatch'):updater.prepare(selected,root)
    event=threading.Event();event.set()
    with pytest.raises(InterruptedError):updater.prepare(selected,root,event)
    assert (root/'keep.txt').read_text()=='old app'
    (root/'.git').mkdir()
    assert not updater.portable_root(root)


@pytest.mark.skipif(os.name!='nt',reason='Windows replacement helper')
@pytest.mark.parametrize('fail_runtime',[False,True])
def test_windows_swap_and_runtime_failure_rollback(tmp_path,fail_runtime):
    import shutil
    root=tmp_path/'Installed App_日本';root.mkdir()
    stage=tmp_path/'.neotrix-update-test';stage.mkdir()
    payload=stage/'payload';payload.mkdir()
    code=tmp_path/'stub.cs'
    code.write_text('using System; using System.IO; class Stub { static int Main(string[] args) { return File.Exists(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"fail-runtime")) ? 9 : 0; }}')
    compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler),'/nologo','/out:'+str(root/'Neotrix Prism.exe'),str(code)],check=True,capture_output=True)
    shutil.copy2(root/'Neotrix Prism.exe',payload/'Neotrix Prism.exe')
    for folder,version in ((root,'0.6.0'),(payload,'0.7.0')):
        (folder/'portable.json').write_text(json.dumps({'product':updater.PRODUCT,'platform':'windows-x64','version':version}))
    (root/'marker').write_text('old');(payload/'marker').write_text('new')
    if fail_runtime:(payload/'fail-runtime').touch()
    backup=tmp_path/'Installed App_日本.previous-test'
    status=tmp_path/'result.json';job=tmp_path/'job.json'
    job.write_text(json.dumps({'root':str(root),'stage':str(stage),'payload':str(payload),'backup':str(backup),
                               'wait_pids':[],'restart':False,'version':'0.7.0','status':str(status)},ensure_ascii=False),encoding='utf-8')
    script=Path(__file__).resolve().parents[1]/'scripts/apply-update.ps1'
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Job',str(job)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    report=json.loads(status.read_text(encoding='utf-8-sig'))
    assert report['state']==('failed' if fail_runtime else 'complete')
    assert (root/'marker').read_text()==('old' if fail_runtime else 'new')
    if not fail_runtime:assert (backup/'marker').read_text()=='old'
