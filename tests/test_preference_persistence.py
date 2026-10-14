import json
import multiprocessing
from pathlib import Path
import pytest
from neotrix_prism.storage import Settings,atomic_json,user_dir


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setenv('NEOTRIX_USER_DIR',str(tmp_path/'prefs'))


def test_stale_window_saves_preserve_favorites_and_other_settings():
    one,two=Settings(),Settings()
    one.favorite(r'R:\Shell')
    two.data['sound_volume']=25;two.save()
    assert Settings().data['favorites']==[r'R:\Shell']
    assert Settings().data['sound_volume']==25
    one.recent(r'R:\KAI')
    assert Settings().data['sound_volume']==25
    two.favorite(r'R:\KAI')
    assert Settings().data['favorites']==[r'R:\Shell',r'R:\KAI']
    one.favorite(r'R:\Shell')
    assert Settings().data['favorites']==[r'R:\KAI']


def test_separate_store_survives_legacy_writer_and_disconnected_storage():
    settings=Settings();settings.favorite(r'\\DisconnectedServer\Relay\Shell')
    legacy=dict(settings.data);legacy['favorites']=[];atomic_json(settings.path,legacy)
    assert Settings().data['favorites']==[r'\\DisconnectedServer\Relay\Shell']
    settings.reload()
    assert settings.data['favorites']==[r'\\DisconnectedServer\Relay\Shell']


def test_corruption_backup_recovery_and_manual_restore():
    settings=Settings();settings.favorite(r'R:\Shell');settings.favorite(r'R:\KAI')
    settings.favorites_path.write_text('{broken',encoding='utf-8')
    recovered=Settings()
    assert recovered.data['favorites']==[r'R:\Shell',r'R:\KAI']
    assert 'recovered' in recovered.recovery_notice.lower()
    recovered.save()
    assert list(settings.backup_dir.glob('corrupt-favorites-*.raw'))
    recovered.favorite(r'R:\Shell')
    snapshot=next(p for p,items in recovered.favorite_backups() if r'R:\Shell' in items)
    recovered.restore_favorites(snapshot)
    assert set(Settings().data['favorites'])=={r'R:\Shell',r'R:\KAI'}


def test_bom_and_partially_invalid_lists_keep_valid_entries():
    (user_dir()/'settings.json').write_text(json.dumps({'favorites':[r'R:\Shell',None,'',r'R:\KAI']}),encoding='utf-8-sig')
    assert Settings().data['favorites']==[r'R:\Shell',r'R:\KAI']


def test_first_launch_migrates_and_backs_up_without_user_action():
    atomic_json(user_dir()/'settings.json',{'favorites':[r'R:\Shell']})
    settings=Settings()
    assert settings.favorites_path.exists()
    assert settings.favorite_backups()[0][1]==[r'R:\Shell']


def _favorite_process(directory,path,ready,start):
    import os
    os.environ['NEOTRIX_USER_DIR']=directory
    settings=Settings();ready.put(True);start.wait(10);settings.favorite(path)


def test_two_process_saves_preserve_both_additions(tmp_path):
    context=multiprocessing.get_context('spawn')
    ready=context.Queue();start=context.Event()
    processes=[context.Process(target=_favorite_process,args=(str(tmp_path/'prefs'),path,ready,start))
               for path in (r'R:\Shell',r'R:\KAI')]
    for process in processes:process.start()
    for _ in processes:assert ready.get(timeout=10)
    start.set()
    for process in processes:
        process.join(15);assert process.exitcode==0
    assert set(Settings().data['favorites'])=={r'R:\Shell',r'R:\KAI'}
