"""Interface sound: soft, spatial cues timed to the motion they accompany.

The cues are pre-rendered by scripts/build_sounds.py into assets/sounds (one
key, one shared room). Playback keeps a few audio streams open and writes a
whole cue into a free one, so triggering costs about 0.1 ms on the UI thread
and the cue starts within one audio period; idle streams are suspended. Cues
are panned and pitched by where things are on screen: the grid plays like a
keyboard, low on the left and high on the right.

Sound is silent, never broken, when audio is unavailable, muted in Settings,
offscreen or under tests. NEOTRIX_SOUND overrides: 0 (off), 1 (force on),
mute (full path at zero volume) or log (record cues without audio).
"""
import os
import time
import wave
from pathlib import Path
from PySide6.QtCore import QObject, QEvent, QTimer, Qt, QByteArray, Signal
from PySide6.QtWidgets import QAbstractButton, QCheckBox, QComboBox, QMenu, QRadioButton

try:
    from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices
except ImportError:  # a runtime without QtMultimedia stays silent
    QAudioSink = None

FOLDER = Path(__file__).resolve().parents[1]/'assets'/'sounds'
RATE, CHANNELS = 48000, 2
MAX_VOICES = 14
WARM_VOICES = 10  # a refresh wave can hold ten cues at once
SUSPEND_AFTER_MS = 2500
LAUNCH_MS = 95  # the refresh bounce crouches for 95 ms before artwork leaves the ground

# Shortest gap between repeats of a cue family (ms), so fast pointer sweeps,
# typing and key repeat stay musical instead of chattering.
# Accents that may skip a beat rather than open a new stream mid-animation.
LIGHT = ('hover', 'hover-soft', 'wave', 'shuffle', 'select', 'press', 'menu')

GAPS = {'hover': 70, 'hover-soft': 55, 'select': 45, 'shuffle': 160, 'press': 35, 'menu': 80,
        'toggle': 60, 'wave': 22, 'nav': 60, 'open': 120, 'back': 120}

FAMILIES = {'open': ('open-left', 'open-center', 'open-right'),
            'hover': tuple(f'hover-{i}' for i in range(5)),
            'wave': tuple(f'wave-{i}' for i in range(7)),
            'press': tuple(f'press-{i}' for i in range(3))}


def family(name):
    """Rate-limit group of a cue: 'hover-3' -> 'hover', 'nav-projects' -> 'nav'."""
    if name in GAPS:
        return name
    stem = name.rsplit('-', 1)[0]
    if stem in FAMILIES:
        return stem
    head = name.split('-')[0]
    return head if head in ('nav', 'toggle') else name


def mode():
    """'on', 'off', 'mute' or 'log' for this process."""
    forced = os.environ.get('NEOTRIX_SOUND', '').strip().lower()
    if forced in ('0', 'off', 'false'):
        return 'off'
    if forced in ('mute', 'log'):
        return forced
    if forced in ('1', 'on', 'true'):
        return 'on'
    from PySide6.QtGui import QGuiApplication
    if os.environ.get('PYTEST_CURRENT_TEST') or QGuiApplication.platformName() in ('offscreen', 'minimal'):
        return 'off'
    return 'on'


def load(path):
    """PCM bytes of a 48 kHz stereo 16-bit WAV, or None."""
    try:
        with wave.open(str(path), 'rb') as clip:
            if (clip.getframerate(), clip.getnchannels(), clip.getsampwidth()) != (RATE, CHANNELS, 2):
                return None
            return clip.readframes(clip.getnframes())
    except (OSError, EOFError, wave.Error):
        return None


class Voice:
    """One open output stream in push mode; a cue is written whole into it."""

    def __init__(self, device, fmt, size):
        self.sink = QAudioSink(device, fmt)
        self.sink.setBufferSize(size)
        self.io = self.sink.start()
        self.size = self.sink.bufferSize()
        self.busy_until = 0.0

    def ok(self):
        return self.io is not None and self.sink.error() == QAudio.Error.NoError

    def free(self, now):
        return now >= self.busy_until and self.sink.bytesFree() >= self.size-64

    def play(self, data, volume, seconds):
        if self.sink.state() == QAudio.State.SuspendedState:
            self.sink.resume()
        self.sink.setVolume(volume)
        written = self.io.write(data)
        self.busy_until = time.monotonic()+seconds+.03
        return written == len(data)

    def suspend(self):
        if self.sink.state() in (QAudio.State.ActiveState, QAudio.State.IdleState):
            self.sink.suspend()

    def close(self):
        self.sink.stop()


class SoundEngine(QObject):
    """Plays named cues from assets/sounds for one window."""
    played = Signal(str, float)  # cue name, linear gain: for capture and tests

    def __init__(self, window, folder=FOLDER):
        super().__init__(window)
        self.window = window
        self.folder = Path(folder)
        self.mode = mode()
        self.clips, self.seconds = {}, {}
        self.voices = []
        self.last = {}
        self.timers = set()
        self.press_turn = 0
        self.pool = WARM_VOICES
        self.available = False
        if self.mode == 'off':
            return
        for path in sorted(self.folder.glob('*.wav')):
            data = load(path)
            if data:
                self.clips[path.stem] = QByteArray(data)
                self.seconds[path.stem] = len(data)/(RATE*CHANNELS*2)
        if not self.clips:
            return
        if self.mode == 'log':
            self.available = True
            return
        if QAudioSink is None:
            return
        self.format = QAudioFormat()
        self.format.setSampleRate(RATE)
        self.format.setChannelCount(CHANNELS)
        self.format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        longest = max(len(c) for c in self.clips.values())
        self.buffer_size = min(longest+RATE*CHANNELS*2//5, RATE*CHANNELS*2*5)
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self.reset)
        self.available = not QMediaDevices.defaultAudioOutput().isNull()
        self.idle = QTimer(self)
        self.idle.setSingleShot(True)
        self.idle.timeout.connect(self.rest)
        self.warmer = QTimer(self)
        self.warmer.timeout.connect(self.warm)

    # ------------------------------------------------------------ settings

    def settings(self):
        return getattr(self.window, 'settings', None)

    def wanted(self, hover=False):
        settings = self.settings()
        data = settings.data if settings else {}
        if not self.available or not data.get('sound', True):
            return False
        return not hover or data.get('sound_hover', True)

    def volume(self, gain):
        settings = self.settings()
        level = max(0, min(100, int((settings.data if settings else {}).get('sound_volume', 70))))/100
        if QAudioSink is not None:
            level = QAudio.convertVolume(level, QAudio.VolumeScale.LogarithmicVolumeScale, QAudio.VolumeScale.LinearVolumeScale)
        return 0.0 if self.mode == 'mute' else max(0.0, min(1.0, level*gain))

    # ------------------------------------------------------------ voices

    def voice(self, light=False):
        now = time.monotonic()
        for voice in self.voices:
            if voice.free(now):
                return voice
        if light:
            # Opening a stream costs 7-20 ms on this thread: grow the pool in the
            # background instead, and let this accent pass.
            self.pool = min(MAX_VOICES, max(self.pool, len(self.voices)+1))
            if not self.warmer.isActive():
                self.warmer.start(220)
            return None
        if len(self.voices) < MAX_VOICES:
            voice = Voice(QMediaDevices.defaultAudioOutput(), self.format, self.buffer_size)
            if voice.ok():
                self.voices.append(voice)
                return voice
            voice.close()
            return None
        return None  # every voice is singing: a quiet cue drops rather than cutting another off

    def warm(self):
        """Open streams ahead of time, one per tick, so bursts never stall a frame."""
        if not self.available or len(self.voices) >= self.pool:
            self.warmer.stop()
            return
        voice = Voice(QMediaDevices.defaultAudioOutput(), self.format, self.buffer_size)
        if voice.ok():
            self.voices.append(voice)
            voice.suspend()
        else:
            voice.close()
            self.warmer.stop()

    def prepare(self, delay=2500):
        """Warm the stream pool after the opening sequence has settled."""
        if self.available and self.mode in ('on', 'mute') and QAudioSink is not None:
            QTimer.singleShot(delay, self, lambda: self.warmer.start(220))

    def rest(self):
        for voice in self.voices:
            voice.suspend()

    def reset(self):
        """The default output changed: reopen streams on the new device."""
        for voice in self.voices:
            voice.close()
        self.voices = []
        self.available = not QMediaDevices.defaultAudioOutput().isNull()

    def shutdown(self):
        self.available = False
        for timer in list(self.timers):
            timer.stop()
        self.timers.clear()
        if self.mode in ('on', 'mute'):
            for voice in self.voices:
                voice.close()
        self.voices = []

    # ------------------------------------------------------------ playing

    def play(self, name, gain=1.0, delay=0, hover=False):
        """Play cue `name` (a file in assets/sounds) after `delay` ms."""
        if name not in self.clips or not self.wanted(hover):
            return False
        if delay > 0:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setTimerType(Qt.PreciseTimer)
            def fire():
                self.timers.discard(timer)
                timer.deleteLater()
                self.play(name, gain, 0, hover)
            timer.timeout.connect(fire)
            self.timers.add(timer)
            timer.start(int(delay))
            return True
        group = family(name)
        now = time.monotonic()*1000
        gap = GAPS.get(group, 0)
        key = name if group == 'wave' else group  # different notes may overlap; one note may not stutter
        if gap and now-self.last.get(key, -1e9) < gap:
            return False
        self.last[key] = now
        if self.mode == 'log':
            self.played.emit(name, gain)
            return True
        voice = self.voice(light=group in LIGHT)
        if voice is None:
            return False
        if not voice.play(self.clips[name], self.volume(gain), self.seconds[name]):
            return False
        self.idle.start(int(self.seconds[name]*1000)+SUSPEND_AFTER_MS)
        self.played.emit(name, gain)
        return True

    def at(self, family_name, x, gain=1.0, delay=0, hover=False):
        """A positional cue: x is 0 (left edge of the window) to 1 (right edge)."""
        names = FAMILIES[family_name]
        index = max(0, min(len(names)-1, int(max(0.0, min(.999, x))*len(names))))
        return self.play(names[index], gain, delay, hover)

    def press(self):
        self.press_turn = (self.press_turn+1) % len(FAMILIES['press'])
        return self.play(FAMILIES['press'][self.press_turn])

    def wave(self, arrivals, limit=8):
        """Refresh: one pluck per artwork as the wave front lifts it.

        `arrivals` holds (delay ms, x 0..1, note or None). Notes come from x
        (grid cards: left low, right high) unless given (list rows climb the
        scale in arrival order). Dense waves are thinned evenly, and later
        plucks fade, so the wave reads as one gesture.
        """
        if not arrivals or not self.wanted():
            return 0
        arrivals = sorted(arrivals, key=lambda a: a[0])
        if len(arrivals) > limit:
            # Keep the first and the farthest arrival, spread the rest evenly.
            arrivals = [arrivals[round(i*(len(arrivals)-1)/(limit-1))] for i in range(limit)]
        names = FAMILIES['wave']
        played, last = 0, {}
        for rank, (delay, x, note) in enumerate(arrivals):
            index = note if note is not None else int(max(0.0, min(.999, x))*len(names))
            name = names[max(0, min(len(names)-1, index))]
            at = delay+LAUNCH_MS
            if at-last.get(name, -1e9) < 45:
                continue
            last[name] = at
            self.play(name, 1.0-.45*rank/max(1, len(arrivals)-1), at)
            played += 1
        return played

    # ------------------------------------------------------------ widgets

    def wire(self, root):
        """Tactile press and hover sounds for buttons, and a soft pop for menus."""
        for button in root.findChildren(QAbstractButton):
            self.attach(button)
        for menu in root.findChildren(QMenu):
            menu.aboutToShow.connect(lambda: self.play('menu'))
        for combo in root.findChildren(QComboBox):
            container = combo.view().parentWidget()
            if container is not None:
                container.installEventFilter(self)

    def attach(self, button):
        if not getattr(button, '_sound_wired', False):
            button._sound_wired = True
            button.installEventFilter(self)

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.MouseButtonPress and isinstance(watched, QAbstractButton):
            if (watched.isEnabled() and event.button() == Qt.LeftButton and not getattr(watched, 'silent_press', False)
                    and not isinstance(watched, (QCheckBox, QRadioButton))):
                self.press()
        elif kind == QEvent.Enter and isinstance(watched, QAbstractButton):
            if watched.isEnabled() and watched.window().isActiveWindow():
                self.play('hover-soft', .8, hover=True)
        elif kind == QEvent.Show and not isinstance(watched, QAbstractButton):
            self.play('menu')
        return False
