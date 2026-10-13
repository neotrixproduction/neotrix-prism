"""Ambient idle motion: one shared clock for living gradients and floating artwork.

Ambient time only advances while the window is visible, active and recently
used. When any of those stop being true, time decelerates smoothly to a halt
instead of freezing mid-step, and the timer stops, so an idle app costs nothing.
Reduced motion stops it entirely.
"""
import time
from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QCursor, QGuiApplication


class Ambient(QObject):
    FPS = 30
    SLEEP_AFTER = 75.0      # seconds without pointer or keyboard input
    RAMP = 1.6              # seconds to ease in or out of motion

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.time = 0.0
        self.level = 0.0
        self.listeners = []
        self.last_input = time.monotonic()
        self.last_tick = None
        self.cursor = QCursor.pos()
        self.ticks = 0
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(1000 // self.FPS)
        self.timer.timeout.connect(self.tick)
        # A slow watchdog wakes the clock on input after it has gone to sleep.
        self.watch = QTimer(self)
        self.watch.setInterval(400)
        self.watch.timeout.connect(self.poll)
        self.watch.start()
        app = QGuiApplication.instance()
        if app:
            app.applicationStateChanged.connect(lambda *_: self.poll())

    def subscribe(self, widget, every=1):
        """Repaint `widget` on every nth ambient frame while it is visible."""
        self.listeners.append((widget, max(1, every)))

    def touched(self):
        self.last_input = time.monotonic()
        self.poll()

    def wanted(self):
        window = self.window
        settings = getattr(window, 'settings', None)
        if settings and settings.data.get('reduced_motion', False):
            return False
        if not window.isVisible() or window.isMinimized():
            return False
        app = QGuiApplication.instance()
        offscreen = app and app.platformName() == 'offscreen'
        if not offscreen and app.applicationState() != Qt.ApplicationActive:
            return False
        return time.monotonic()-self.last_input < self.SLEEP_AFTER

    def poll(self):
        position = QCursor.pos()
        if position != self.cursor:
            self.cursor = position
            self.last_input = time.monotonic()
        if self.wanted() and not self.timer.isActive():
            self.last_tick = None
            self.timer.start()

    def tick(self):
        now = time.monotonic()
        dt = 0.0 if self.last_tick is None else min(.1, now-self.last_tick)
        self.last_tick = now
        position = QCursor.pos()
        if position != self.cursor:
            self.cursor = position
            self.last_input = now
        target = 1.0 if self.wanted() else 0.0
        step = dt/self.RAMP
        self.level = min(target, self.level+step) if target > self.level else max(target, self.level-step)
        # Eased level: motion gathers and loses speed gently rather than linearly.
        eased = self.level*self.level*(3-2*self.level)
        self.time += dt*eased
        self.ticks += 1
        for widget, every in list(self.listeners):
            try:
                if self.ticks % every == 0 and widget.isVisible():
                    widget.update()
            except RuntimeError:
                self.listeners.remove((widget, every))
        if self.level <= 0 and target <= 0:
            self.timer.stop()

    def stop(self):
        self.level = 0.0
        self.timer.stop()


def ambient_time(widget):
    """Shared ambient seconds for a widget's window (0 when unavailable)."""
    window = widget.window() if hasattr(widget, 'window') else None
    ambient = getattr(window, 'ambient', None)
    return ambient.time if ambient else 0.0
