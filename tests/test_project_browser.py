import json
from pathlib import Path
import pytest
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from neotrix_prism.project_metadata import StageStore, inferred_stage, inheritance_snapshot
from neotrix_prism.storage import exclusive_lock
from neotrix_prism import indexer


@pytest.fixture
def project(tmp_path,monkeypatch):
    monkeypatch.setenv('NEOTRIX_USER_DIR',str(tmp_path/'prefs'))
    project=tmp_path/'project';project.mkdir()
    return project


def test_stage_concurrent_edit_and_lock(project):
    one,two=StageStore(project),StageStore(project)
    old=two.load()['fingerprint']
    saved=one.save([project/'scene_v001.blend'],'layout',old)
    with pytest.raises(RuntimeError,match='another workstation'):
        two.save([project/'scene_v002.blend'],'lighting',old)
    with exclusive_lock(one.path.with_suffix('.lock')):
        with pytest.raises(RuntimeError,match='another session'):
            two.save([project/'scene_v002.blend'],'lighting',saved['fingerprint'])
    assert one.load()['assignments']=={'scene_v001.blend':'layout'}
    with pytest.raises(ValueError):one.save([project.parent/'outside.blend'],'lighting',saved['fingerprint'])


def test_stage_offline_cache_and_corrupt_document(project):
    store=StageStore(project)
    store.save([project/'scene.blend'],'lighting',None)
    store.project=project/'disconnected';store.path=store.project/'_TOOLS/neotrix-prism/stages.json'
    document=store.load()
    assert document['assignments']=={'scene.blend':'lighting'}
    assert not document['writable']
    with pytest.raises(OSError):store.save([store.project/'scene.blend'],'layout',None)
    corrupt=StageStore(project)
    corrupt.path.write_text('{broken')
    with pytest.raises(ValueError):corrupt.load()


def test_stage_readonly_and_inheritance(project,monkeypatch):
    store=StageStore(project)
    saved=store.save([project/'scene_v001.blend'],'lighting',None)
    snapshot=inheritance_snapshot(project/'scene_v001.blend')
    assert snapshot[2]=='lighting'
    snapshot[0].save([project/'scene_v002.blend'],snapshot[2],snapshot[1])
    assert store.load()['assignments']=={'scene_v001.blend':'lighting','scene_v002.blend':'lighting'}
    monkeypatch.setattr('neotrix_prism.project_metadata.os.access',lambda *args:False)
    document=store.load()
    assert not document['writable']
    with pytest.raises(PermissionError):store.save([project/'scene_v003.blend'],'layout',document['fingerprint'])


def test_variant_recipe_and_stage_inference(project):
    shot='03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/'
    paths={'03_PRODUCTION/WORK/3D/ASSETS/projects/NTX_Vertical_0010_v001.blend':('modelling','Vertical'),
           shot+'PROJECTS/NTX_Vertical_0010_v002.blend':('unassigned','Vertical'),
           shot+'COMPOSITING/projects/NTX_Vertical_0010_v003.aep':('compositing','Vertical'),
           '03_PRODUCTION/WORK/GRAPHIC_DESIGN/projects/NTX_Summer_v001.ai':('other','Summer')}
    # The template's shot stage folders: SHOTS/<shot>/PROJECTS/<STAGE>.
    for folder,stage in (('MODELLING','modelling'),('RIGGING','rigging'),('LAYOUT','layout'),
                         ('ANIMATION','animation'),('FX','fx'),('LIGHTING','lighting'),
                         ('COMPOSITING','compositing'),('OTHERS','other')):
        paths[shot+f'PROJECTS/{folder}/NTX_Vertical_0010_v010.blend']=(stage,'Vertical')
    for relative,(expected,variant) in paths.items():
        path=project/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
        file=indexer.parse(path,project)
        assert inferred_stage(file)==expected,relative
        assert file['variant']==variant


def test_icon_candidates_fallback_and_cache(project,monkeypatch,tmp_path):
    app=QApplication.instance() or QApplication([])
    from neotrix_prism import project_browser
    icons=project/'_TOOLS/icon';icons.mkdir(parents=True)
    template=tmp_path/'template';template.mkdir()
    monkeypatch.setattr(project_browser,'TEMPLATE_ICON',template)
    cache=tmp_path/'cache/project.png'
    image=QImage(64,64,QImage.Format_ARGB32);image.fill(QColor('#ff0000'));image.save(str(icons/'project.png'))
    assert project_browser.read_icon(project,cache)==str(cache)
    assert QImage(str(cache)).pixelColor(20,20)==QColor('#ff0000')
    (icons/'project.png').write_bytes(b'corrupt')
    image.fill(QColor('#0000ff'));image.save(str(template/'project.png'))
    fallback = project_browser.read_icon(project,cache)
    assert fallback == project_browser.themed_artwork(project)
    assert not cache.exists()  # Template art is not custom artwork; name-based art wins.
    image.fill(QColor('#ff0000'));image.save(str(icons/'project.png'))
    assert project_browser.read_icon(project,cache)==str(cache)
    assert project_browser.read_icon(tmp_path/'disconnected-project',cache)==str(cache)
    (icons/'project.png').unlink()
    assert project_browser.read_icon(project,cache)==project_browser.themed_artwork(project)
    assert not cache.exists()
    (icons/'project.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#00ff00"/></svg>')
    assert project_browser.read_icon(project,cache)==str(cache)
    assert QImage(str(cache)).pixelColor(20,20)==QColor('#00ff00')
