import json
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication, QWidget
from neotrix_prism import apps, storage
from neotrix_prism.project_metadata import StageStore


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('NEOTRIX_USER_DIR', str(tmp_path/'prefs'))


@pytest.mark.parametrize('document', ['[]', 'null', '{"roots":null,"apps":[],"favorites":false,"recent":17}'])
def test_malformed_preferences_recover(document):
    (storage.user_dir()/'settings.json').write_text(document)
    settings=storage.Settings()
    assert settings.data['roots']==[storage.DEFAULT_ROOT]
    assert settings.data['apps']=={}
    assert settings.data['favorites']==[]
    assert settings.data['recent']==[]


@pytest.mark.parametrize('document', ['[]', 'null', '{"format":1,"assignments":{"a.blend":[]}}'])
def test_malformed_shared_stage_metadata_is_actionable(tmp_path, document):
    project=tmp_path/'project';project.mkdir()
    store=StageStore(project)
    store.path.parent.mkdir(parents=True)
    store.path.write_text(document)
    with pytest.raises(ValueError):store.load()


def test_corrupt_activity_records_are_ignored():
    records=[[], None, {}, {'time':'bad','event':'invalid'},
             {'time':1,'event':'File opened','path':['bad']},
             {'time':2,'event':'File opened','path':'demo.blend'}]
    (storage.user_dir()/'activity.jsonl').write_text('\n'.join(json.dumps(r) for r in records)+'\n{broken\n')
    assert storage.history()==[records[-1]]


def test_launch_and_reveal_use_separate_arguments(tmp_path, monkeypatch):
    source=tmp_path/'shot & scene.blend';source.write_bytes(b'fixture')
    executable=tmp_path/'creative app.exe';executable.write_bytes(b'fixture')
    calls=[]
    monkeypatch.setattr(apps.subprocess,'Popen',lambda args,**kwargs:calls.append((args,kwargs)))
    apps.open_file(source,'Blender',{'Blender':str(executable)})
    assert calls[-1]==([str(executable),str(source)],{'shell':False})
    apps.reveal(source)
    assert calls[-1]==(['explorer.exe','/select,',str(source)],{'shell':False})
    with pytest.raises(FileNotFoundError,match='unavailable'):apps.open_file(tmp_path/'missing.blend','Blender',{})
    with pytest.raises(FileNotFoundError,match='Settings'):apps.open_file(source,'Blender',{'Blender':str(tmp_path/'missing.exe')})


def test_bridge_rejects_malformed_commands_and_accepts_disconnect(monkeypatch):
    import requests
    from neotrix_prism import bridge
    app=QApplication.instance() or QApplication([])
    parent=QWidget()
    monkeypatch.setattr(bridge,'PORT',0)
    connection=bridge.Bridge(parent)
    url=f'http://127.0.0.1:{connection.server.server_port}'
    try:
        assert requests.get(url,timeout=3).json()['status']=='ready'
        for body in ([],None,{'app':'photoshop','command':'arbitraryScript'}, {'app':'unknown','command':'saveVersion'}):
            response=requests.post(url,data=json.dumps(body),timeout=3)
            assert response.status_code==400
        response=requests.post(url,json={'app':'photoshop','command':'disconnect'},timeout=3)
        assert response.status_code==202
        app.processEvents()
    finally:
        connection.close()
