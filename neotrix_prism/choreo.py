"""Motion-graphics layers: kinetic type, shared-element zoom and the refresh wave.

All of them are finite, mouse-transparent, keep glyphs at native size and
pixel-aligned, and disappear entirely once they settle.
"""
import math
import time
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF, QEvent, QSize, QVariantAnimation, QAbstractAnimation
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient,
                           QPainterPath, QFontMetricsF, QFont)
from PySide6.QtWidgets import QWidget, QLabel, QAbstractScrollArea
from . import physics
from .motion import clock, enabled, snap, soften, spring
from .physics import SNAPPY


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def _smooth(value):
    value = _clamp(value)
    return value*value*(3-2*value)


class KineticLabel(QLabel):
    """Per-glyph kinetic type: letters rise through the label's edge while their
    tracking converges; the previous text lifts away first. At rest the QLabel
    paints itself, so selection, accessibility and fonts are untouched.
    """
    OUT_MS, OUT_STEP, HANDOFF = 170, 10, 110

    def __init__(self, text='', parent=None, rise=20, stagger=24, tracking=3.0, quiet=0):
        super().__init__(text, parent)
        self.rise, self.stagger, self.tracking, self.quiet = rise, stagger, tracking, quiet
        self.elapsed = -1.0
        self.outgoing = ''
        self.changed_at = 0.0
        self.layouts = {}

    def setText(self, text):
        previous = self.text()
        super().setText(text)
        now = time.monotonic()*1000
        rapid = now-self.changed_at < self.quiet
        self.changed_at = now
        if text == previous:
            return
        if rapid or not self.isVisible():
            self.stop()
        else:
            self.play(previous)

    def play(self, previous=''):
        metrics = QFontMetricsF(self.font())
        too_wide = metrics.horizontalAdvance(self.text()) > self.contentsRect().width()
        if not enabled(self) or self.textFormat() == Qt.RichText or too_wide:
            self.stop()
            return
        self.outgoing = previous if metrics.horizontalAdvance(previous) <= self.contentsRect().width() else ''
        self.layouts.clear()
        lead = self.HANDOFF if self.outgoing else 0
        duration = max(self.OUT_MS+len(self.outgoing)*self.OUT_STEP,
                       lead+len(self.text())*self.stagger+physics.settle_time(.46, .68))
        self.elapsed = 0.0  # hide the new text before the clock's first tick
        self.update()
        clock(self, '_kinetic', duration, self.advance, self.stop)

    def advance(self, value):
        self.elapsed = float(value)
        self.update()

    def stop(self):
        animation = getattr(self, '_kinetic', None)
        if animation:
            animation.stop()
        self.elapsed = -1.0
        self.outgoing = ''
        self.update()

    def glyphs(self, text, metrics, box):
        """Glyph origins that include kerning with the preceding letter."""
        key = (text, box.width(), int(self.alignment()))
        if key not in self.layouts:
            width = metrics.horizontalAdvance(text)
            align = self.alignment()
            left = (box.left()+(box.width()-width)/2 if align & Qt.AlignHCenter else
                    box.right()-width if align & Qt.AlignRight else box.left())
            self.layouts[key] = [(i, ch, left+metrics.horizontalAdvance(text[:i+1])-metrics.horizontalAdvance(ch))
                                 for i, ch in enumerate(text) if not ch.isspace()]
        return self.layouts[key]

    def paintEvent(self, event):
        if self.elapsed < 0:
            return super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        metrics = QFontMetricsF(self.font())
        box = QRectF(self.contentsRect())
        dpr = self.devicePixelRatioF()
        if self.alignment() & Qt.AlignTop:
            baseline = box.top()+metrics.ascent()
        else:
            baseline = box.top()+(box.height()-metrics.height())/2+metrics.ascent()
        t = self.elapsed
        for i, ch, x in self.glyphs(self.outgoing, metrics, box) if self.outgoing else ():
            q = _clamp((t-i*self.OUT_STEP)/self.OUT_MS)
            if q < 1:
                p.setOpacity(1-q)
                p.drawText(QPointF(snap(x, dpr), snap(baseline-self.rise*.55*q*q, dpr)), ch)
        lead = self.HANDOFF if self.outgoing else 0
        centre = (len(self.text())-1)/2
        for i, ch, x in self.glyphs(self.text(), metrics, box):
            local = t-lead-i*self.stagger
            if local <= 0:
                continue
            k = physics.progress(local, .46, .68)
            p.setOpacity(_clamp(local/150))
            p.drawText(QPointF(snap(x+self.tracking*(i-centre)*(1-k), dpr),
                               snap(baseline+self.rise*(1-k), dpr)), ch)


class StatusLine(KineticLabel):
    """The footer status: one quiet line that elides in the middle (the full
    text becomes its tooltip) and rolls in gently instead of announcing."""

    def __init__(self, text=''):
        super().__init__('', None, rise=8, stagger=5, tracking=0, quiet=450)
        self.full = ''
        self.setWordWrap(False)
        self.setText(text)

    def fitted(self, text):
        width = max(40, self.contentsRect().width())
        return QFontMetricsF(self.font()).elidedText(text, Qt.ElideMiddle, width)

    def setText(self, text):
        self.full = text
        shown = self.fitted(text)
        self.setToolTip(text if shown != text else '')
        super().setText(shown)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        shown = self.fitted(self.full)
        if shown != QLabel.text(self):
            QLabel.setText(self, shown)  # re-fit silently; only new text animates
            self.setToolTip(self.full if shown != self.full else '')


class Hairline(QWidget):
    """Indeterminate progress as a 2 px line of light: a soft comet glides
    along a faint track, tinted by the live scene, and the whole line fades
    in and out on a spring. Mouse-transparent; quiet by design."""

    PERIOD = 1700

    def __init__(self, parent=None, width=150):
        super().__init__(parent)
        self.setFixedSize(width, 14)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.presence, self.phase, self.active = 0.0, .5, False
        self.travel = QVariantAnimation(self)
        self.travel.setStartValue(0.0)
        self.travel.setEndValue(1.0)
        self.travel.setDuration(self.PERIOD)
        self.travel.setLoopCount(-1)
        self.travel.valueChanged.connect(self.advance)
        super().hide()

    def advance(self, value):
        self.phase = float(value)
        self.update()

    def set_active(self, active):
        """Show while work runs; the line fades out after it ends."""
        self.active = bool(active)
        if not enabled(self):
            self.travel.stop()
            self.presence, self.phase = (1.0 if active else 0.0), .5
            self.setVisible(self.active)
            return
        if self.active:
            self.show()
            if self.travel.state() != QAbstractAnimation.State.Running:
                self.travel.start()
        def fade(value):
            self.presence = max(0.0, float(value))
            self.update()
        def settled():
            if not self.active:
                self.travel.stop()
                self.hide()
        spring(self, 'presence', 1.0 if self.active else 0.0, fade, value=self.presence,
               feel=SNAPPY if self.active else (.5, 1.0), done=settled)

    def pause(self, paused):
        """Hold the comet while the window is minimised."""
        state = self.travel.state()
        if paused:
            if state == QAbstractAnimation.State.Running:
                self.travel.pause()
        elif self.active and self.isVisible() and enabled(self):
            if state == QAbstractAnimation.State.Paused:
                self.travel.resume()
            elif state == QAbstractAnimation.State.Stopped:
                self.travel.start()

    def hideEvent(self, event):
        self.travel.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        if self.presence <= .01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, y = self.width(), self.height()/2
        surface = getattr(self.window(), 'surface', None)
        tint = surface.scene_colors()[1].lighter(430) if surface is not None and hasattr(surface, 'scene_colors') else QColor('#d9d2ff')
        def colour(base, alpha):
            result = QColor(base)
            result.setAlpha(int(max(0, min(255, alpha*self.presence))))
            return result
        p.setPen(QPen(colour(QColor(255, 255, 255), 20), 1.5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(2, y), QPointF(w-2, y))
        # The comet eases across (slow at the edges, quick through the middle),
        # entering and leaving beyond the ends so the line never ticks.
        u = self.phase
        eased = .5-.5*math.cos(math.pi*u)
        length = w*.36
        head = -length*.4+(w+length*.8)*eased
        trail = QLinearGradient(head-length, y, head, y)
        trail.setColorAt(0, colour(tint, 0))
        trail.setColorAt(.7, colour(tint, 120))
        trail.setColorAt(1, colour(QColor(255, 255, 255), 230))
        start, end = max(2.0, head-length), min(w-2.0, head)
        if end <= start:
            return
        p.save()
        p.setClipRect(QRectF(1, 0, w-2, self.height()))
        for width, alpha in ((6, .22), (2, 1.0)):
            pen = QPen(QBrush(trail), width, Qt.SolidLine, Qt.RoundCap)
            p.setOpacity(alpha)
            p.setPen(pen)
            p.drawLine(QPointF(start, y), QPointF(end, y))
        p.restore()


class Shockwave(QWidget):
    """Refresh light that radiates from the orb across the whole workspace.

    Rings are light, not geometry: the same radial field also lights the edges
    of every card it crosses, so content catches the wave as it passes. Callers
    use `delay_for` to make artwork jump exactly when the front reaches it.
    """
    motion_layer = True
    SPEED = 1650.0

    def __init__(self, host):
        super().__init__(host)
        self.origin = QPointF()
        self.page = None
        self.tint = QColor('#d9d3ff')
        self.elapsed = -1.0
        self.reach = 1.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        host.installEventFilter(self)
        self.hide()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def delay_for(self, point):
        return QLineF(self.origin, QPointF(point)).length()/self.SPEED*1000

    def fire(self, origin, page, tint):
        if not enabled(self):
            return
        # Light keeps the scene's hue but is lifted toward white so it reads as glow.
        hue = QColor(tint).hsvHueF()
        self.origin, self.page = QPointF(origin), page
        self.tint = QColor.fromHsvF(max(0.0, hue), .32, 1.0)
        self.setGeometry(self.parentWidget().rect())
        corners = (QPointF(0, 0), QPointF(self.width(), 0), QPointF(0, self.height()), QPointF(self.width(), self.height()))
        self.reach = max(QLineF(self.origin, c).length() for c in corners)
        self.show()
        self.raise_()
        clock(self, '_wave', self.reach/self.SPEED*1000+560, self.advance, self.reset_wave)

    def advance(self, value):
        self.elapsed = float(value)
        self.update()

    def reset_wave(self):
        animation = getattr(self, '_wave', None)
        if animation:
            animation.stop()
        self.elapsed = -1.0
        self.page = None
        self.hide()

    def ring(self, radius, width, strength):
        outer = radius+width*.4
        field = QRadialGradient(self.origin, outer)
        def colour(alpha):
            result = QColor(self.tint)
            result.setAlpha(int(_clamp(alpha, 0, 255)))
            return result
        field.setColorAt(0, colour(0))
        field.setColorAt(_clamp((radius-width)/outer), colour(0))
        field.setColorAt(_clamp(radius/outer), colour(strength))
        field.setColorAt(1, colour(0))
        return field

    def targets(self):
        """Rounded rectangles on the current page that can catch the light."""
        page, host = self.page, self.parentWidget()
        if page is None or not page.isVisible():
            return
        # The layer sits at the host's origin, so host coordinates are ours.
        for widget in page.findChildren(QWidget):
            if not widget.isVisible() or getattr(widget, 'motion_layer', False):
                continue
            boxes = getattr(widget, 'hit_boxes', None)
            if boxes is not None:
                offset = QPointF(widget.mapTo(host, widget.rect().topLeft()))
                for _, rect in boxes:
                    yield QRectF(rect).translated(offset), 22
            elif widget.objectName() in ('card', 'featureTile', 'hero') or isinstance(widget, QAbstractScrollArea):
                target = widget.viewport() if isinstance(widget, QAbstractScrollArea) else widget
                yield QRectF(QPointF(target.mapTo(host, target.rect().topLeft())), QSize(target.width(), target.height())), 18

    def paintEvent(self, event):
        if self.elapsed < 0:
            return
        t = self.elapsed/1000
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        front = self.SPEED*t
        # A broad leading swell, a crisp echo behind it, and a faint wake.
        for lag, width, strength in ((0.0, 230, 118), (.1, 60, 92), (.2, 420, 34)):
            radius = self.SPEED*(t-lag)
            fade = _clamp(1-radius/self.reach)**.7
            if radius > 0 and fade > 0:
                p.fillRect(self.rect(), self.ring(radius, width, strength*fade))
        flash = _clamp(1-t/.42)
        if flash > 0:
            core = QRadialGradient(self.origin, 190)
            glow = QColor(self.tint)
            glow.setAlpha(int(150*flash*flash))
            core.setColorAt(0, glow)
            glow.setAlpha(0)
            core.setColorAt(1, glow)
            p.fillRect(self.rect(), core)
        fade = _clamp(1-front/self.reach)**.5
        if front > 0 and fade > 0:
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(QBrush(self.ring(front, 260, 245*fade)), 1.6)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            for rect, radius in self.targets():
                p.drawRoundedRect(rect.adjusted(.8, .8, -.8, -.8), radius, radius)


class ZoomThrough(QWidget):
    """Shared-element navigation: the chosen card's colour field opens into the
    next level while its artwork flies forward and through the camera.

    Labels are never scaled; the card title only travels and fades.
    """
    motion_layer = True
    DURATION = 860

    def __init__(self, host, card, art, colors, artwork, title, snapshot=None, snapshot_at=QPointF()):
        super().__init__(host)
        self.card, self.art = QRectF(card), QRectF(art)
        self.colors, self.artwork, self.title = colors, artwork, title
        self.snapshot, self.soft, self.snapshot_at = snapshot, soften(snapshot), QPointF(snapshot_at)
        self.elapsed = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(host.rect())
        self.show()
        self.raise_()
        clock(self, '_zoom', self.DURATION, self.advance, self.finish)

    def advance(self, value):
        self.elapsed = float(value)
        self.update()

    def finish(self):
        animation = getattr(self, '_zoom', None)
        if animation:
            animation.stop()
        self.hide()
        self.snapshot = self.soft = self.artwork = None
        self.deleteLater()

    @staticmethod
    def blend(a, b, k):
        return a+(b-a)*k

    def paintEvent(self, event):
        t = self.elapsed
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        dpr = self.devicePixelRatioF()
        full = QRectF(self.rect())
        # 1. The previous grid recedes into soft focus.
        leave = _clamp(t/230)
        if self.snapshot is not None and leave < 1:
            drift = QPointF(self.snapshot_at.x(), snap(self.snapshot_at.y()+16*leave*leave, dpr))
            p.setOpacity((1-leave)*(1-min(1, leave*1.8)))
            p.drawPixmap(drift, self.snapshot)
            if self.soft is not None:
                p.setOpacity((1-leave)*min(1, leave*1.8))
                size = self.snapshot.deviceIndependentSize()
                p.drawPixmap(QRectF(drift, size), self.soft, QRectF(self.soft.rect()))
        # 2. The card's colour field opens to the page.
        grow = physics.progress(t, .5, .86)
        rect = QRectF(self.blend(self.card.left(), full.left(), grow), self.blend(self.card.top(), full.top(), grow),
                      self.blend(self.card.width(), full.width(), grow), self.blend(self.card.height(), full.height(), grow))
        field = 1-_smooth((t-340)/420)
        if field > 0:
            shape = QPainterPath()
            shape.addRoundedRect(rect, 22+4*grow, 22+4*grow)
            first, last = QColor(self.colors[0]), QColor(self.colors[1])
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, first)
            gradient.setColorAt(1, last)
            p.setOpacity(field)
            p.fillPath(shape, gradient)
            bloom = QRadialGradient(rect.center(), max(rect.width(), rect.height())*.62)
            light = QColor(255, 236, 255, int(105*math.sin(math.pi*_clamp(t/620))))
            bloom.setColorAt(0, light)
            light.setAlpha(0)
            bloom.setColorAt(1, light)
            p.fillPath(shape, bloom)
            p.setPen(QPen(QColor(255, 255, 255, int(60*(1-grow))), 1))
            p.setBrush(Qt.NoBrush)
            p.drawPath(shape)
            # The title rides the expanding field's corner, then lets go.
            words = 1-_clamp(t/210)
            if words > 0 and self.title:
                font = QFont(self.font())
                font.setPixelSize(17)
                font.setWeight(QFont.DemiBold)
                p.setFont(font)
                p.setPen(QColor('#fffaff'))
                p.setOpacity(field*words)
                lift = 10*_clamp(t/210)
                base = QPointF(snap(rect.left()+22, dpr), snap(rect.bottom()-67-lift, dpr))
                p.drawText(QRectF(base, QSize(int(self.card.width())-44, 26)), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        # 3. Artwork flies forward to centre stage, then through the camera.
        if self.artwork is not None and not self.artwork.isNull():
            travel = physics.progress(t, .54, .7)
            through = _smooth((t-400)/420)
            centre = QPointF(self.blend(self.art.center().x(), full.center().x(), travel),
                             self.blend(self.art.center().y(), full.top()+full.height()*.4, travel))
            size = self.blend(self.art.width(), min(full.width(), full.height())*.36, travel)*(1+.9*through)
            p.setOpacity(1-through)
            p.save()
            p.translate(centre)
            p.rotate(-6*(1-travel)+4*through)
            p.drawPixmap(QRectF(-size/2, -size/2, size, size), self.artwork, QRectF(self.artwork.rect()))
            p.restore()
