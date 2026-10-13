"""Interaction-driven Qt motion. Springs keep their velocity across interruptions,
every effect settles at rest, and reduced motion snaps straight to the end state."""
import math
from PySide6.QtCore import Qt, QVariantAnimation, QEasingCurve, QRectF, QSize, QPointF, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QRadialGradient, QConicalGradient, QPainterPath, QIcon
from PySide6.QtWidgets import (QPushButton, QWidget, QStylePainter, QStyleOptionButton, QStyle, QGraphicsEffect,
                               QScrollArea, QSplitter, QSplitterHandle)
from . import physics
from .physics import SNAPPY, POP, FLUID


def enabled(widget):
    window = widget.window() if hasattr(widget, 'window') else None
    settings = getattr(window, "settings", None)
    return not (settings and settings.data.get("reduced_motion", False))


def snap(value, dpr=1.0):
    """Pixel-aligned translation keeps native glyphs crisp while they travel."""
    return round(value*dpr)/dpr


def tween(owner, key, start, end, update, duration=220, curve=QEasingCurve.OutCubic):
    old = getattr(owner, key, None)
    if old:
        old.stop()
        old.deleteLater()
    if not enabled(owner):
        update(end)
        setattr(owner, key, None)
        return None
    animation = QVariantAnimation(owner)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setDuration(duration)
    animation.setEasingCurve(curve)
    animation.valueChanged.connect(update)
    setattr(owner, key, animation)
    animation.start()
    return animation


def spring(owner, key, target, update, value=None, velocity=None, feel=FLUID, delay=0, precision=None, done=None):
    """Physics-driven motion that retargets without losing momentum."""
    if not enabled(owner):
        physics.cancel(owner, key)
        update(target)
        if done:
            done()
        return None
    return physics.animate(owner, key, target, update, value, velocity, feel, delay, precision, done)


def clock(owner, key, duration, update, done=None):
    """A linear millisecond clock for painters that sample many staggered springs.

    Linear time does not mean linear motion: each sampled trajectory is a spring.
    """
    animation = tween(owner, key, 0.0, float(duration), update, max(1, int(duration)), QEasingCurve.Linear)
    if done:
        if animation:
            animation.finished.connect(done)
        else:
            done()
    return animation


def refresh_motion(elapsed, delay, amplitude):
    """(offset, vertical stretch, tilt) of artwork riding the refresh wave.

    Stretch follows speed and squash follows the landing, so artwork reads as
    having weight rather than sliding on a curve.
    """
    if delay is None or elapsed < 0:
        return 0.0, 1.0, 0.0
    displacement, velocity = physics.bounce(elapsed-delay)
    if not displacement and not velocity:
        return 0.0, 1.0, 0.0
    stretch = min(.09, abs(velocity)*.006)-min(.08, max(0.0, displacement)*.32)
    return displacement*amplitude, 1+stretch, velocity*.22


class MotionButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.hover = self.press = self.pop = 0.0
        self.turn = 1.0
        self.reveal = 1.0
        self.ripple = 1.0
        self.ripple_origin = QPointF()
        self.bob = self.tilt = 0.0
        self.stretch = 1.0
        self.setCursor(Qt.PointingHandCursor)
        self.pressed.connect(lambda: self.animate_press(1.0))
        self.released.connect(lambda: self.animate_press(0.0))

    def animate_press(self, target):
        # A firm press, then a jelly release that briefly swells past rest.
        spring(self, 'press', target, self.set_press, value=self.press,
               feel=(.15, .9) if target else (.34, .45))

    def refresh_wave(self, delay=0):
        if not enabled(self):
            return
        def step(elapsed):
            self.bob, self.stretch, self.tilt = refresh_motion(elapsed, delay, 7)
            self.update()
        clock(self, '_bob', delay+physics.BOUNCE_MS, step, self.reset_wave)

    def reset_wave(self):
        animation = getattr(self, '_bob', None)
        if animation:
            animation.stop()
        self.bob, self.stretch, self.tilt = 0.0, 1.0, 0.0
        self.update()

    def hop(self):
        """Selection feedback: the icon jumps and turns a full revolution in 3D."""
        spring(self, 'pop', 0.0, self.set_pop, value=self.pop, velocity=11, feel=POP)
        def turn(value):
            self.turn = float(value)
            self.update()
        spring(self, 'turn', 1.0, turn, value=0.0, feel=(.62, .62))

    def intro(self, delay=0):
        if not enabled(self):
            return
        self.reveal = 0.0
        self.update()
        spring(self, 'reveal', 1.0, self.set_reveal, value=0.0, feel=POP, delay=delay)

    def set_pop(self, value):
        self.pop = float(value)
        self.update()

    def set_reveal(self, value):
        self.reveal = float(value)
        self.update()

    def set_press(self, value):
        self.press = float(value)
        self.update()

    def set_hover(self, value):
        self.hover = float(value)
        self.update()

    def mousePressEvent(self, event):
        self.ripple_origin = event.position()
        def advance(value):
            self.ripple = float(value)
            self.update()
        tween(self, '_ripple', 0.0, 1.0, advance, 620, QEasingCurve.OutCubic)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        spring(self, 'hover', 1.0, self.set_hover, value=self.hover, feel=SNAPPY)
        super().enterEvent(event)

    def leaveEvent(self, event):
        spring(self, 'hover', 0.0, self.set_hover, value=self.hover, feel=(.4, 1.0))
        super().leaveEvent(event)

    def paint_artwork(self, p, artwork, size):
        # Icon-only controls paint their artwork in perspective with float
        # transforms, so lift, turn and squash glide instead of stepping.
        from . import art3d
        reveal = max(0.0, min(1.0, self.reveal))
        hover = max(0.0, self.hover)
        lift = -2.5*hover-5*self.pop+self.bob-14*(1-self.reveal)
        scale = 1+.1*hover-.08*self.press+.16*self.pop
        mode = QIcon.Normal if self.isEnabled() else QIcon.Disabled
        state = QIcon.On if self.isChecked() else QIcon.Off
        pixmap = artwork.pixmap(size, self.devicePixelRatioF(), mode, state)
        art3d.paint(p, pixmap, QPointF(self.width()/2, self.height()/2), size.width(),
                    yaw=360*(1-self.turn)-14*hover, pitch=6*hover, roll=self.tilt-7*self.pop,
                    scale=scale, stretch=self.stretch, opacity=reveal, lift=lift)

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        p = QStylePainter(self)
        # Copy first: PySide exposes option.icon by reference into the option.
        artwork = QIcon(option.icon) if not self.text() and not option.icon.isNull() else None
        if artwork is not None:
            option.icon = QIcon()
        p.drawControl(QStyle.CE_PushButton, option)
        if artwork is not None:
            self.paint_artwork(p, artwork, QSize(self.iconSize()))
        hover = max(0.0, min(1.0, self.hover))
        if hover > .01 and self.isEnabled():
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor(255, 255, 255, int(12*hover)))
            p.setPen(QPen(QColor(255, 255, 255, int(78*hover)), 1.1))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)
        if enabled(self) and 0 < self.ripple < 1:
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)
            p.setClipPath(clip)
            radius = max(self.width(), self.height())*1.15*self.ripple
            fade = (1-self.ripple)**1.4
            p.setPen(QPen(QColor(255, 255, 255, int(120*fade)), 1.4))
            p.setBrush(QColor(255, 255, 255, int(30*fade)))
            p.drawEllipse(self.ripple_origin, radius, radius)


class MotionIcon(QWidget):
    def __init__(self, name, size=100):
        super().__init__()
        self.name, self.hover, self.reveal = name, 0.0, 1.0
        self.pointer = QPointF()
        self.artwork = None
        self.bob = self.tilt = 0.0
        self.stretch = 1.0
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_hover(self, value):
        self.hover = float(value)
        self.update()

    def set_artwork(self, path):
        self.artwork = QIcon(path)
        self.update()

    def refresh_wave(self, delay=0):
        if not enabled(self):
            return
        amplitude = min(24, self.height()*.14)
        def step(elapsed):
            self.bob, self.stretch, self.tilt = refresh_motion(elapsed, delay, amplitude)
            self.update()
        clock(self, '_bob', delay+physics.BOUNCE_MS, step, self.reset_wave)

    def reset_wave(self):
        animation = getattr(self, '_bob', None)
        if animation:
            animation.stop()
        self.bob, self.stretch, self.tilt = 0.0, 1.0, 0.0
        self.update()

    def engage(self, target):
        spring(self, 'hover', target, self.set_hover, value=self.hover, feel=POP if target else (.5, .9))

    def track(self, point):
        if enabled(self):
            self.pointer = point
            self.update()

    def appear(self, delay=0):
        if not enabled(self):
            self.reveal = 1.0
            self.update()
            return
        self.reveal = 0.0
        self.update()
        spring(self, 'reveal', 1.0, self.set_reveal, value=0.0, feel=POP, delay=delay)

    def set_reveal(self, value):
        self.reveal = float(value)
        self.update()

    def paintEvent(self, event):
        from .design import icon
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        p.setOpacity(max(0.0, min(1.0, self.reveal*1.4)))
        # Artwork floats independently of the surface: depth comes from the
        # pointer offset, changing shadow and spring settlement.
        art = int(min(w, h)*.70)
        angle = -11*self.hover+self.pointer.x()*7*self.hover+(1-self.reveal)*24+self.tilt
        footprint = abs(math.cos(math.radians(angle)))+abs(math.sin(math.radians(angle)))
        grow = .55+.45*self.reveal
        sx = min((grow+.16*self.hover)*(2-self.stretch), (w-4)/(art*footprint))
        sy = min((grow+.12*self.hover)*self.stretch, (h-4)/(art*footprint))
        extent = art*max(sx, sy)*footprint/2+1
        x = max(extent, min(w-extent, w/2+self.pointer.x()*10*self.hover))
        y = max(extent, min(h-extent, h/2+(1-self.reveal)*58-self.hover*13+self.pointer.y()*8*self.hover+self.bob))
        p.translate(x, y)
        shadow = QRadialGradient(0, h*.32, w*.48)
        shadow.setColorAt(0, QColor(10, 5, 36, int(95*max(0.0, min(1.0, self.hover)))))
        shadow.setColorAt(1, QColor(10, 5, 36, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(shadow)
        p.drawEllipse(QRectF(-w*.48, h*.15, w*.96, h*.3))
        p.rotate(angle)
        p.scale(sx, sy)
        # Keep a safe apron for spring rotation, lift and pointer parallax.
        p.drawPixmap(-art // 2, -art // 2, (self.artwork or icon(self.name, art)).pixmap(art, art))


class PageEffect(QGraphicsEffect):
    """Opacity plus a pixel-aligned rise; glyphs are never scaled."""
    def __init__(self, widget, rise=22):
        super().__init__(widget)
        self.amount, self.rise = 0.0, rise

    def advance(self, value):
        self.amount = float(value)
        self.update()

    def boundingRectFor(self, rect):
        reach = abs(self.rise)+2
        return rect.adjusted(0, -reach, 0, reach)

    def draw(self, painter):
        device = painter.device()
        dpr = device.devicePixelRatioF() if device else 1.0
        offset = snap(self.rise*(1-self.amount), dpr)
        opacity = max(0.0, min(1.0, self.amount*1.3))
        if opacity >= 1 and not offset:
            self.drawSource(painter)
            return
        if opacity <= 0:
            return
        # drawSource ignores painter opacity, so composite the device-resolution
        # source pixmap instead; it is cached by Qt between frames.
        origin = QPoint()  # filled in place by Qt
        pixmap = self.sourcePixmap(Qt.LogicalCoordinates, origin, QGraphicsEffect.PadToEffectiveBoundingRect)
        painter.save()
        painter.setOpacity(opacity)
        painter.translate(0, offset)
        painter.drawPixmap(origin, pixmap)
        painter.restore()


def reveal_page(widget, delay=0, rise=22, start=0.0, feel=FLUID):
    """Bring a block in with a rise; an interrupted reveal continues from where it is."""
    physics.cancel(widget, 'reveal')
    if not enabled(widget):
        if isinstance(widget.graphicsEffect(), PageEffect):
            widget.setGraphicsEffect(None)
        return
    parent = widget.parentWidget()
    while parent:
        if parent.graphicsEffect():
            return
        parent = parent.parentWidget()
    effect = widget.graphicsEffect()
    if effect is not None and not isinstance(effect, PageEffect):
        return
    if effect is None:
        effect = PageEffect(widget, rise)
        effect.amount = start
        widget.setGraphicsEffect(effect)
    else:
        effect.rise = rise
    def finished():
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)
    spring(widget, 'reveal', 1.0, effect.advance, value=effect.amount, feel=feel, delay=delay, done=finished)


def motion_blocks(root):
    """Visible content blocks in reading order; plain containers are opened up."""
    found = []
    def visit(parent):
        for child in parent.findChildren(QWidget, '', Qt.FindDirectChildrenOnly):
            if not child.isVisible() or getattr(child, 'motion_layer', False) or isinstance(child, QSplitterHandle):
                continue
            if isinstance(child, QScrollArea) and child.widget():
                visit(child.widget())
            elif type(child) is QWidget or isinstance(child, QSplitter):
                visit(child)
            else:
                found.append(child)
    visit(root)
    def place(widget):
        point = widget.mapTo(root, QPoint(0, 0))
        return point.y()//24, point.x()
    return sorted(found, key=place)


def cascade(root, delay=0, rise=24, step=55):
    """Stagger a page's blocks in; grids and lists run their own inner cascade."""
    if not enabled(root):
        return
    for index, block in enumerate(motion_blocks(root)):
        lag = delay+min(index*step, 440)
        if hasattr(block, 'play_entrance'):
            block.play_entrance(lag)
        else:
            reveal_page(block, lag, rise)


def snapshot(widget):
    """A transparent capture of a widget's content (no window background), so
    a departing page never flashes an opaque fill over the living backdrop."""
    from PySide6.QtGui import QPixmap, QRegion
    dpr = widget.devicePixelRatioF()
    pixmap = QPixmap(max(1, round(widget.width()*dpr)), max(1, round(widget.height()*dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)
    widget.render(pixmap, QPoint(), QRegion(), QWidget.DrawChildren)
    return pixmap


def soften(pixmap):
    """A cheap, one-off soft-focus copy for dissolves (never redrawn per frame)."""
    if pixmap is None or pixmap.isNull():
        return None
    w, h = pixmap.width(), pixmap.height()
    small = pixmap.scaled(max(1, w//14), max(1, h//14), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return small.scaled(max(1, w//3), max(1, h//3), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


class SceneTransition(QWidget):
    """The outgoing page leaves fast through a soft-focus dissolve, travelling the
    same way as the sidebar selection; the incoming page's live blocks cascade in
    underneath. No opaque underlay, so the colour field behind never flashes.
    """
    motion_layer = True
    EXIT_MS = 320

    def __init__(self, stack, outgoing, origin=None, direction=1):
        super().__init__(stack)
        self.outgoing, self.soft = outgoing, soften(outgoing)
        self.amount = 0.0
        self.origin = QRectF(origin) if origin else None
        self.direction = direction
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(stack.rect())
        self.show()
        self.raise_()
        cascade(stack.currentWidget(), 90, 26*direction)
        animation = tween(self, '_scene', 0.0, 1.0, self.advance, self.EXIT_MS, QEasingCurve.Linear)
        if animation:
            animation.finished.connect(self.finish)
        else:
            self.finish()

    def advance(self, value):
        self.amount = float(value)
        self.update()

    def finish(self):
        if getattr(self, '_scene', None):
            self._scene.stop()
        self.hide()
        self.outgoing = self.soft = None
        self.deleteLater()

    def paintEvent(self, event):
        if self.outgoing is None or self.outgoing.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        t = self.amount
        presence = 1-t*t*(3-2*t)
        dpr = self.devicePixelRatioF()
        # Accelerating departure: the page gathers speed as it leaves.
        offset = QPointF(0, snap(-self.direction*34*t*t, dpr))
        focus = min(1.0, t*1.9)
        p.setOpacity(presence*(1-focus))
        p.drawPixmap(offset, self.outgoing)
        if self.soft:
            p.setOpacity(presence*focus)
            p.drawPixmap(QRectF(offset, QSize(self.width(), self.height())), self.soft, QRectF(self.soft.rect()))


class OrbButton(MotionButton):
    """Workspace-tinted glass with an honest task-driven progress ring."""
    def __init__(self, text="Refresh", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(84, 84)
        self.setAccessibleName("Refresh projects")
        self.busy, self.angle = False, 0.0
        self.activity = 0.0
        self.swap, self.previous_text = 1.0, ''
        self.spin = QVariantAnimation(self)
        self.spin.setStartValue(0.0)
        self.spin.setEndValue(360.0)
        self.spin.setDuration(1600)
        self.spin.setLoopCount(-1)
        self.spin.valueChanged.connect(self.advance_ring)

    def advance_ring(self, value):
        self.angle = float(value)
        self.update()

    def set_swap(self, value):
        self.swap = float(value)
        self.update()

    def set_busy(self, busy):
        changed = self.busy != busy
        self.busy = busy
        if changed:
            def advance(value):
                self.activity = float(value)
                self.update()
            spring(self, 'activity', 1.0 if busy else 0.0, advance, value=self.activity, feel=POP if busy else SNAPPY)
        text = "Stop" if busy else "Refresh"
        if text != self.text():
            self.previous_text = self.text()
            self.setText(text)
            # The label rolls: old word lifts away while the new one rises in.
            spring(self, 'swap', 1.0, self.set_swap, value=0.0, feel=(.34, .8))
        self.setAccessibleName("Cancel current operation" if busy else "Refresh projects")
        if busy and enabled(self) and self.isVisible() and not self.window().isMinimized():
            self.spin.start()
        else:
            self.spin.stop()
            self.angle = 45
        self.update()

    def hideEvent(self, event):
        self.spin.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.set_busy(self.busy)

    def paint_label(self, p):
        p.setRenderHint(QPainter.TextAntialiasing)
        box = QRectF(self.rect())
        dpr = self.devicePixelRatioF()
        settle = max(0.0, min(1.0, self.reveal*1.6-.6))
        swap = max(0.0, min(1.2, self.swap))
        clip = QPainterPath()
        clip.addEllipse(QRectF(9, 9, 66, 66))
        p.setClipPath(clip)
        p.setPen(QColor("#ffffff"))
        if self.previous_text and swap < 1:
            p.setOpacity(settle*(1-min(1.0, swap*1.6)))
            p.drawText(box.translated(0, snap(-16*swap, dpr)), Qt.AlignCenter, self.previous_text)
        p.setOpacity(settle*min(1.0, swap*1.4))
        p.drawText(box.translated(0, snap(16*(1-swap), dpr)), Qt.AlignCenter, self.text())

    def paintEvent(self, event):
        surface = getattr(self.window(), 'surface', None)
        colors = surface.scene_colors() if surface else [QColor('#243d66'), QColor('#234858'), QColor('#101b30')]
        drift = getattr(surface, 'refresh_phase', 0.0)
        def tinted(color, brightness, alpha):
            result = QColor(color).lighter(brightness)
            result.setAlpha(alpha)
            return result
        tint = tinted(colors[1], 420, 255)
        # Idle life: the orb breathes and its iridescent rim slowly turns.
        from .ambient import ambient_time
        t = ambient_time(self) if enabled(self) else 0.0
        breath = .5+.5*math.sin(t*1.15)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.save()
        p.translate(42, 42)
        scale = (1 + .10 * self.hover - .09 * self.press + .035*self.activity + .08*self.pop + .018*breath)*max(0.0, self.reveal)
        p.scale(scale, scale)
        glow = QRadialGradient(0, 0, 41)
        glow.setColorAt(0, tinted(tint, 100, round(28+22*self.hover+18*drift+20*breath)))
        glow.setColorAt(1, tinted(tint, 100, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(-41, -41, 82, 82))
        body = QLinearGradient(-24-12*drift, -35, 24+12*drift, 35)
        body.setColorAt(0, tinted(colors[0], 400, 140))
        body.setColorAt(.45, tinted(colors[1], 400, 92))
        body.setColorAt(1, tinted(colors[2], 340, 165))
        p.setBrush(body)
        hue = tint.hsvHueF() if tint.hsvHueF() >= 0 else .7
        rim = QConicalGradient(0, 0, -t*38)
        for stop, shift, alpha in ((0, None, 220), (.22, .12, 170), (.5, None, 120), (.74, -.12, 170), (1, None, 220)):
            rim.setColorAt(stop, QColor(255, 255, 255, alpha) if shift is None else QColor.fromHsvF((hue+shift) % 1.0, .5, 1.0, alpha/255))
        p.setPen(QPen(rim, 1.4))
        p.drawEllipse(QRectF(-34, -34, 68, 68))
        glass = QLinearGradient(-25,-33,18,33)
        glass.setColorAt(0,QColor(255,255,255,68))
        glass.setColorAt(.42,QColor(255,255,255,12))
        glass.setColorAt(.58,QColor(255,255,255,2))
        glass.setColorAt(1,tinted(tint,150,44))
        p.setPen(Qt.NoPen);p.setBrush(glass)
        p.drawEllipse(QRectF(-33,-33,66,66))
        highlight = QRadialGradient(-14-self.hover*8+20*drift+3*math.sin(t*.7),-22+2*math.cos(t*.6),38)
        highlight.setColorAt(0,QColor(255,255,255,int(110+40*max(0.0, self.hover))))
        highlight.setColorAt(.5,QColor(255,255,255,20))
        highlight.setColorAt(1,QColor(255,255,255,0))
        p.setPen(Qt.NoPen)
        p.setBrush(highlight)
        p.drawEllipse(QRectF(-33,-33,66,66))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255,255,255,90), .8))
        p.drawArc(QRectF(-30,-30,60,60),30*16,100*16)
        p.setPen(QPen(tinted(tint,170,95),1.2))
        p.drawArc(QRectF(-31,-31,62,62),210*16,95*16)
        if self.busy:
            p.setPen(QPen(QColor(255,255,255,230), 3, Qt.SolidLine, Qt.RoundCap))
            span = 100 + 65*math.sin(math.radians(self.angle)) if enabled(self) else 100
            p.drawArc(QRectF(-36, -36, 72, 72), int(self.angle * 16), int(span * 16))
            p.setPen(QPen(tinted(tint,160,130),1.5,Qt.SolidLine,Qt.RoundCap))
            p.drawArc(QRectF(-39,-39,78,78),int(-self.angle*16),55*16)
        if self.hasFocus():
            p.setPen(QPen(QColor("#ffffff"), 2, Qt.DotLine))
            p.drawEllipse(QRectF(-39, -39, 78, 78))
        p.restore()
        self.paint_label(p)
