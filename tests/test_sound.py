import json
import re
import wave
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from neotrix_prism import sound
from neotrix_prism.storage import Settings

ROOT = Path(__file__).resolve().parents[1]
SOUNDS = ROOT/'assets'/'sounds'


def cue_names():
    """Every cue the app can ask for, from literal calls and the positional families."""
    source = (ROOT/'neotrix_prism'/'ui.py').read_text(encoding='utf-8')
    names = set(re.findall(r"sound\.play\('([a-z0-9-]+)'[,)]", source))
    names |= {'nav-'+page.lower() for page in ('Projects', 'Favorites', 'Activity', 'Settings')}
    names |= {'nav-whoosh-down', 'nav-whoosh-up', 'toggle-on', 'toggle-off', 'sidebar-open', 'sidebar-close',
              'favorite-add', 'favorite-remove', 'hover-soft', 'menu'}
    for family in sound.FAMILIES.values():
        names |= set(family)
    return names


def test_every_cue_has_a_valid_sound_file():
    source = json.loads((SOUNDS/'SOURCE.json').read_text(encoding='utf-8'))
    recorded = {item['file'] for item in source['sounds']}
    for name in sorted(cue_names()):
        path = SOUNDS/f'{name}.wav'
        assert path.is_file(), name
        assert path.name in recorded, name
        with wave.open(str(path)) as clip:
            assert (clip.getframerate(), clip.getnchannels(), clip.getsampwidth()) == (48000, 2, 2), name
            assert 0.1 < clip.getnframes()/48000 < 4.0, name


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv('NEOTRIX_USER_DIR', str(tmp_path/'prefs'))
    monkeypatch.setenv('NEOTRIX_SOUND', 'log')
    QApplication.instance() or QApplication([])

    class Host:
        settings = Settings()

    from PySide6.QtCore import QObject
    parent = QObject()
    result = sound.SoundEngine(parent)
    result.window = Host
    heard = []
    result.played.connect(lambda name, gain: heard.append((name, round(gain, 2))))
    yield result, heard, Host.settings
    result.shutdown()


def test_sound_is_silent_by_default_under_tests(tmp_path, monkeypatch):
    monkeypatch.delenv('NEOTRIX_SOUND', raising=False)
    assert sound.mode() == 'off'
    monkeypatch.setenv('NEOTRIX_SOUND', '0')
    assert sound.mode() == 'off'


def test_positional_cues_follow_the_screen(engine):
    engine, heard, settings = engine
    assert engine.at('hover', 0.0) and engine.at('open', .5)
    engine.last.clear()
    assert engine.at('hover', .99)
    assert heard == [('hover-0', 1.0), ('open-center', 1.0), ('hover-4', 1.0)]


def test_rate_limits_and_settings_gate_cues(engine):
    engine, heard, settings = engine
    assert engine.play('hover-2', hover=True)
    assert not engine.play('hover-3', hover=True)  # within the hover gap
    settings.data['sound_hover'] = False
    engine.last.clear()
    assert not engine.play('hover-2', hover=True)
    assert engine.play('press-0')
    settings.data['sound'] = False
    assert not engine.play('done')
    assert not engine.play('missing-cue')
    assert [name for name, _ in heard] == ['hover-2', 'press-0']


def test_refresh_wave_thins_orders_and_fades(engine):
    engine, heard, settings = engine
    arrivals = [(i*30, i/20, None) for i in range(20)]
    assert engine.wave(arrivals) == 8
    QTest.qWait(1000)
    names = [name for name, _ in heard]
    gains = [gain for _, gain in heard]
    assert len(names) == 8 and names[0] == 'wave-0' and names[-1] == 'wave-6'
    assert gains == sorted(gains, reverse=True)


def test_volume_and_sound_settings_are_validated(tmp_path, monkeypatch):
    monkeypatch.setenv('NEOTRIX_USER_DIR', str(tmp_path/'prefs'))
    settings = Settings()
    assert (settings.data['sound'], settings.data['sound_hover'], settings.data['sound_volume']) == (True, True, 70)
    settings.data.update(sound='yes', sound_volume=True)
    settings.save()
    settings = Settings()
    assert settings.data['sound'] is True and settings.data['sound_volume'] == 70
    settings.data['sound_volume'] = 300
    settings.save()
    assert Settings().data['sound_volume'] == 70
