"""Resolution-independent surfaces with living, interaction-driven light."""
import math
from PySide6.QtCore import QRectF, Qt, Signal, QPointF, QEvent, QLineF
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QRadialGradient, QPainterPath, QPen, QRegion, QImage, QPixmap
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel, QHBoxLayout, QAbstractScrollArea
from . import physics
from .ambient import ambient_time
from .motion import spring, MotionIcon, enabled
from .physics import POP, SETTLE


def _mix(a, b, amount):
    amount = max(0.0, min(1.0, amount))
    return QColor(*[round(a.getRgb()[i]*(1-amount)+b.getRgb()[i]*amount) for i in range(3)])


# Aurora blobs: (palette slot, hue shift, saturation, value, alpha, radius,
# home x, home y, x speed, y speed, phase). Speeds are radians per ambient second.
AURORA = ((0, 0.0, .62, .80, 120, .62, .22, .78, .21, .17, 0.0),
          (1, .09, .58, .78, 105, .58, .80, .16, .16, .23, 1.7),
          (0, -.11, .52, .70, 92, .52, .70, .86, .26, .19, 3.1),
          (1, .04, .70, .90, 70, .40, .42, .28, .19, .29, 4.4),
          (0, .18, .45, .74, 58, .46, .08, .18, .23, .14, 5.6))


class Atmosphere(QWidget):
    """The living colour field behind everything.

    A dark scene gradient carries slowly drifting aurora blobs whose hues come
    from the scene. The field is rendered small and cached, so idle motion costs
    a blit per frame. Changing scene floods the new colours outward as a wave
    from where the change began.
    """
    palette_changed = Signal()
    dark = True
    accent = 0.0
    refresh_phase = 0.0
    intro = 1.0
    blend = 1.0
    origin_colors = None
    wave_origin = None
    glow = (.3, .7)
    SCENES = [('#290840','#160b39','#0b1128'),('#151346','#08273d','#080f24'),
              ('#3b0b2b','#290d39','#120d27'),('#033335','#08282d','#071425'),
              ('#0a3020','#0c2626','#0b1425'),('#0b3427','#0d292d','#091622'),
              ('#451609','#2f110e','#170c16')]
    FIELD_SCALE = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = None
        self.frame_key = None
        self.scene_key = 0
        self.current = [QColor(c) for c in self.SCENES[0]]

    def refresh_wave(self, delay=0):
        # An impulse into a critically damped spring is a natural swell-and-fade
        # envelope: light surges with the shockwave, then ebbs without a seam.
        def step(value):
            self.refresh_phase = max(0.0, float(value))
            self.update()
            self.palette_changed.emit()
        spring(self, 'refresh', 0.0, step, value=self.refresh_phase, velocity=10.5, feel=(1.6, 1.0), delay=delay)

    def reset_wave(self):
        physics.cancel(self, 'refresh')
        self.refresh_phase = 0.0
        self.update()
        self.palette_changed.emit()

    def play_intro(self, delay=0):
        """First light: the workspace rises out of black as its glow blooms."""
        if not enabled(self):
            return
        def step(value):
            self.intro = float(value)
            self.update()
        self.intro = 0.0
        spring(self, 'intro', 1.0, step, value=0.0, feel=(1.1, 1.0), delay=delay)

    def focus_scene(self, index, origin=None):
        """Change scene: a SCENES index or three custom colours (dark to darker).
        With an origin the new colours flood outward from that point as a wave;
        without one they crossfade. Never passes through other scenes."""
        if isinstance(index, (list, tuple)):
            colors = [QColor(c) for c in index]
            key = tuple(c.name() for c in colors)
            anchor_seed = sum(c.hue() for c in colors)/97
        else:
            index = max(0, min(len(self.SCENES)-1, int(index)))
            colors, key, anchor_seed = [QColor(c) for c in self.SCENES[index]], index, index
            self.accent = float(index)
        if key == self.scene_key and self.blend >= 1:
            return
        self.origin_colors = self.scene_colors()
        self.scene_key, self.current = key, colors
        self.wave_origin = QPointF(origin) if origin is not None and enabled(self) else None
        def blend(value):
            self.blend = float(value)
            self.frame_key = None
            self.update()
            self.palette_changed.emit()
        momentum = physics.speed(self, 'blend') if self.wave_origin is None else 0.0
        self.blend = 0.0
        spring(self, 'blend', 1.0, blend, value=0.0, velocity=max(0.0, momentum),
               feel=(1.15, 1.0) if self.wave_origin is not None else SETTLE)
        # The light source drifts to each scene's own position like a camera move.
        anchor = (.3+.24*math.sin(anchor_seed), .7+.18*math.cos(anchor_seed))
        def drift(value):
            self.glow = value
            self.frame_key = None
            self.update()
        spring(self, 'glow', anchor, drift, value=self.glow, feel=(1.2, .9))

    def wave_radius(self):
        """Current radius of the scene wave front, in widget pixels."""
        if self.wave_origin is None:
            return 0.0
        corners = (QPointF(0, 0), QPointF(self.width(), 0), QPointF(0, self.height()), QPointF(self.width(), self.height()))
        reach = max(QLineF(self.wave_origin, c).length() for c in corners)
        return reach*1.08*self.blend

    def target_colors(self):
        return [QColor(c) for c in self.current]

    def scene_colors(self):
        """Live colors shared by the workspace and glass controls."""
        target = self.target_colors()
        if self.origin_colors is None or self.blend >= 1:
            return target
        eased = self.blend*self.blend*(3-2*self.blend)
        return [_mix(a, b, eased) for a, b in zip(self.origin_colors, target)]

    def render_field(self, colors, t, w, h):
        """Small aurora image; upscaled smoothly it is indistinguishable from full size."""
        image = QImage(w, h, QImage.Format_RGB32)
        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing)
        drift = self.refresh_phase
        base = QLinearGradient(-w*.35*drift, h*.25*drift, w*(1+.35*drift), h*(1-.3*drift))
        for position, color in zip((0, .48, 1), colors):
            base.setColorAt(position, color)
        p.fillRect(image.rect(), base)
        hues = [c.hsvHueF() if c.hsvHueF() >= 0 else .75 for c in colors]
        gx, gy = self.glow
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        for slot, shift, sat, val, alpha, radius, hx, hy, sx, sy, phase in AURORA:
            x = w*(hx+(gx-.3)*.5+.17*math.sin(t*sx+phase))
            y = h*(hy+(gy-.7)*.4+.15*math.cos(t*sy+phase*1.3))
            colour = QColor.fromHsvF((hues[slot]+shift) % 1.0, sat, val)
            colour.setAlpha(int(min(255, alpha*(1+.55*drift))))
            field = QRadialGradient(x, y, w*radius*(1+.22*drift+.06*math.sin(t*.37+phase)))
            field.setColorAt(0, colour)
            colour.setAlpha(int(colour.alpha()*.35))
            field.setColorAt(.45, colour)
            colour.setAlpha(0)
            field.setColorAt(1, colour)
            p.fillRect(image.rect(), field)
        p.end()
        return image

    def compose(self):
        """The current field at device resolution, rebuilt only when it changes."""
        dpr = self.devicePixelRatioF()
        t = ambient_time(self) if enabled(self) else 0.0
        key = (self.width(), self.height(), dpr, round(t*10), round(self.blend, 3),
               round(self.refresh_phase, 3), self.scene_key, self.glow)
        if self.frame is not None and key == self.frame_key:
            return self.frame
        w, h = max(8, self.width()//self.FIELD_SCALE), max(8, self.height()//self.FIELD_SCALE)
        image = self.render_field(self.target_colors(), t, w, h)
        if self.origin_colors is not None and self.blend < 1:
            before = self.render_field(self.origin_colors, t, w, h)
            if self.wave_origin is not None:
                # The new scene floods outward: mask it with a soft-edged disc
                # (it needs an alpha channel before it can be masked).
                image = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
                mask = QPainter(image)
                mask.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                radius = max(.5, self.wave_radius()/self.FIELD_SCALE)
                edge = QRadialGradient(self.wave_origin/self.FIELD_SCALE, radius)
                edge.setColorAt(0, QColor(0, 0, 0, 255))
                edge.setColorAt(.78, QColor(0, 0, 0, 255))
                edge.setColorAt(1, QColor(0, 0, 0, 0))
                mask.fillRect(image.rect(), edge)
                mask.end()
                layer = QPainter(before)
                layer.drawImage(0, 0, image)
                layer.end()
                image = before
            else:
                eased = self.blend*self.blend*(3-2*self.blend)
                layer = QPainter(before)
                layer.setOpacity(eased)
                layer.drawImage(0, 0, image)
                layer.end()
                image = before
        frame = QPixmap(max(1, round(self.width()*dpr)), max(1, round(self.height()*dpr)))
        frame.setDevicePixelRatio(dpr)
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(QRectF(0, 0, self.width(), self.height()), image)
        painter.end()
        self.frame, self.frame_key = frame, key
        return frame

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_shape()

    def update_shape(self):
        if self.window().isMaximized():
            self.clearMask()
        else:
            shape = QPainterPath()
            shape.addRoundedRect(QRectF(self.rect()), 26, 26)
            self.setMask(QRegion(shape.toFillPolygon().toPolygon()))

    def paint_backdrop(self, painter, widget, rect, target=None):
        """Paint the field that lies beneath `widget`'s `rect` into `target`
        (default `rect`), so content can dissolve into the living backdrop."""
        if self.frame is None:
            return
        offset = widget.mapTo(self, rect.topLeft().toPoint())
        dpr = self.frame.devicePixelRatio()
        source = QRectF(offset.x()*dpr, offset.y()*dpr, rect.width()*dpr, rect.height()*dpr)
        painter.drawPixmap(target or rect, self.frame, source)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.compose())
        dawn = max(0.0, min(1.0, self.intro))
        if self.wave_origin is not None and self.blend < 1:
            # A luminous rim rides the wave front as the new colour arrives.
            radius = self.wave_radius()
            rim = QColor.fromHsvF(self.target_colors()[0].hsvHueF() % 1.0, .38, 1.0)
            ring = QRadialGradient(self.wave_origin, radius+60)
            for stop, alpha in ((0, 0), (max(0.0, (radius-150)/(radius+60)), 0), (radius/(radius+60), 70*(1-self.blend)), (1, 0)):
                rim.setAlpha(int(alpha))
                ring.setColorAt(stop, rim)
            p.setCompositionMode(QPainter.CompositionMode_Screen)
            p.fillRect(self.rect(), ring)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if dawn < 1:
            p.fillRect(self.rect(), QColor(3, 2, 10, round(255*(1-dawn)**1.6)))


class GradientTile(QFrame):
    """A painted gradient stays crisp at every Windows display scale."""
    hover_changed = Signal(float)
    TONES = {"hero": ("#8030ac", "#151344", "#d660de"),
             "Projects": ("#6440a4", "#332463", "#efb375"),
             "Workflows": ("#5143a4", "#24275d", "#54ccea"),
             "Favorites": ("#833b9e", "#392066", "#f885c1"),
             "FavoriteList": ("#6e2f5c", "#3a1f4f", "#ff8cc6"),
             "ActivityList": ("#1f5a63", "#173a52", "#5fe0cf"),
             "Recent": ("#633693", "#28245f", "#8594ed"),
             "Storage": ("#55378c", "#26225d", "#60d8c8")}

    def __init__(self, tone="hero"):
        super().__init__()
        self.tone = tone
        self.hover = 0.0
        self.pointer = QPointF(.75, .18)
        self.sweep = 1.0
        self.refresh_phase = 0.0
        self.wave_ticket = 0
        self.setObjectName("hero" if tone == "hero" else "featureTile")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setMouseTracking(True)

    def showEvent(self, event):
        super().showEvent(event)
        # Child labels and buttons must participate in the same lighting field.
        for child in self.findChildren(QWidget):
            child.setMouseTracking(True)
            child.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseMove and enabled(self):
            self.track_pointer(self.mapFromGlobal(event.globalPosition().toPoint()))
        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event):
        if enabled(self):
            self.track_pointer(event.position())
        super().mouseMoveEvent(event)

    def track_pointer(self, point):
        destination = (point.x()/max(1,self.width()), point.y()/max(1,self.height()))
        def step(value):
            self.pointer = QPointF(*value)
            for artwork in self.findChildren(MotionIcon):
                artwork.track(QPointF((value[0]-.5)*2, (value[1]-.5)*2))
            self.update()
        spring(self, 'pointer', destination, step, value=(self.pointer.x(), self.pointer.y()), feel=(.26, .9))

    def set_sweep(self, value):
        self.sweep = float(value)
        self.update()

    def refresh_wave(self, delay=0):
        if not enabled(self):
            return
        def step(value):
            self.refresh_phase = max(0.0, float(value))
            self.update()
        # Swell-and-ebb envelope from an impulse, timed to the wave front.
        spring(self, 'refresh', 0.0, step, value=self.refresh_phase, velocity=12, feel=(1.3, 1.0), delay=delay)
        spring(self, 'sheen', 1.0, self.set_sweep, value=0.0, feel=(.9, 1.0), delay=delay)

    def reset_wave(self):
        for key in ('refresh', 'sheen'):
            physics.cancel(self, key)
        self.refresh_phase = 0.0
        self.sweep = 1.0
        self.update()

    def set_hover(self, value):
        self.hover = float(value)
        self.update()
        self.hover_changed.emit(self.hover)

    def enterEvent(self, event):
        spring(self, 'hover', 1.0, self.set_hover, value=self.hover, feel=POP)
        spring(self, 'sheen', 1.0, self.set_sweep, value=0.0, feel=(.7, 1.0))
        for artwork in self.findChildren(MotionIcon):
            artwork.engage(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        spring(self, 'hover', 0.0, self.set_hover, value=self.hover, feel=(.5, 1.0))
        for artwork in self.findChildren(MotionIcon):
            artwork.engage(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 24, 24)
        p.setClipPath(path)
        first, last, bloom = self.TONES[self.tone]
        import math
        drift = self.refresh_phase
        base = QLinearGradient(-rect.width()*.35*drift, rect.height()*.3*drift,
                               rect.width()*(1+.35*drift), rect.height()*(1-.3*drift))
        base.setColorAt(0, QColor(first))
        base.setColorAt(1, QColor(last))
        base.setColorAt(0,QColor(first).lighter(135))
        base.setColorAt(1,QColor(last).lighter(140))
        p.setOpacity(.86)
        p.fillPath(path, base)
        p.setOpacity(1)
        glass=QLinearGradient(0,0,rect.width(),rect.height())
        glass.setColorAt(0,QColor(255,255,255,36));glass.setColorAt(1,QColor(255,255,255,15))
        p.fillPath(path,glass)
        glow = QRadialGradient(rect.width() * (.92 - .12 * self.hover-.65*drift), rect.height() * (.08+.45*drift), rect.width() * .63)
        glow.setColorAt(0, QColor(bloom))
        glow.setColorAt(.32, QColor(bloom).lighter(105))
        glow.setColorAt(1, QColor(100, 45, 150, 0))
        p.setOpacity((.28 if self.tone == "hero" else .48) + .15 * self.hover)
        p.fillPath(path, glow)
        p.setOpacity(1)
        if enabled(self) and self.hover > .01:
            light = QRadialGradient(rect.width()*self.pointer.x(), rect.height()*self.pointer.y(), rect.width()*.65)
            light.setColorAt(0, QColor(255,226,255,int(48*min(1,self.hover))))
            light.setColorAt(1, QColor(255,226,255,0))
            p.fillPath(path, light)
        if 0 < self.sweep < 1 and enabled(self):
            x = rect.width()*(-.6+2.2*self.sweep)
            gloss = QLinearGradient(x-rect.width()*.2,0,x+rect.width()*.2,rect.height())
            gloss.setColorAt(0,QColor(255,255,255,0))
            gloss.setColorAt(.5,QColor(255,235,255,35))
            gloss.setColorAt(1,QColor(255,255,255,0))
            p.fillPath(path, gloss)
        sheen = QLinearGradient(0, 0, 0, rect.height())
        sheen.setColorAt(0, QColor(255, 255, 255, int(38 + 70 * self.hover)))
        sheen.setColorAt(.5, QColor(255, 255, 255, 4))
        sheen.setColorAt(1, QColor(255, 255, 255, 13))
        p.setPen(QPen(sheen, 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)


class RecentProjectCard(GradientTile):
    """Square project artwork with live, untransformed typography."""
    clicked = Signal()

    def __init__(self, title, artwork=None):
        super().__init__('Recent')
        self.setFixedSize(148, 148)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('Continue ' + title)
        self.full_title = title
        self.setToolTip(title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 12)
        layout.setSpacing(0)
        self.art = MotionIcon('Projects', 108)
        if artwork:
            self.art.set_artwork(artwork)
        layout.addWidget(self.art, 1, Qt.AlignCenter)
        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.title.setStyleSheet('background:transparent;font-size:13px;')
        self.title.setFixedWidth(128)
        layout.addWidget(self.title, 0, Qt.AlignCenter)

    def showEvent(self, event):
        super().showEvent(event)
        self.title.setText(self.title.fontMetrics().elidedText(self.full_title, Qt.ElideRight, 128))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        self.set_hover(1)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.set_hover(0)
        super().focusOutEvent(event)


class CreativeConstellation(QWidget):
    """Original creative constellation, with generous space for floating artwork."""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(174)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)
        for name, size in [('Projects', 132), ('Workspace', 166), ('Brand', 188),
                           ('Favorites', 154), ('Activity', 124)]:
            layout.addStretch()
            artwork = MotionIcon(name, size)
            layout.addWidget(artwork, 0, Qt.AlignCenter)
        layout.addStretch()

    def resizeEvent(self, event):
        # The constellation fits the minimum desktop width without squeezing text.
        sizes = [132,166,188,154,124]
        ratio = min(1, max(.6, (self.width()-48)/sum(sizes)))
        for artwork, size in zip(self.findChildren(MotionIcon), sizes):
            artwork.setFixedSize(round(size*ratio), round(size*ratio))
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(226, 203, 255, 30), 1))
        p.setBrush(Qt.NoBrush)
        for inset in (0, 24, 48):
            p.drawEllipse(QRectF(self.width()*.08+inset, self.height()*.18+inset*.25,
                                self.width()*.84-inset*2, self.height()*.6-inset*.5))
        p.setPen(Qt.NoPen)
        for x, y in ((.13,.18),(.3,.78),(.57,.12),(.79,.81),(.91,.35)):
            p.setBrush(QColor(255, 225, 255, 140))
            p.drawEllipse(QPointF(self.width()*x,self.height()*y),2,2)


class WorkspaceArt(QWidget):
    """Original layered project folders and creative app tiles, drawn once per paint."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(238, 185)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        from .design import icon
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.translate(12, 8)
        p.rotate(-8)
        for x, y, size, name in [(85, 17, 105, "Workflows"), (47, 48, 123, "Projects")]:
            p.drawPixmap(x, y, icon(name, size).pixmap(size, size))
        p.rotate(8)
        for x, y, name in [(17, 94, "Photoshop"), (157, 112, "After Effects"), (148, 18, "Blender")]:
            p.drawPixmap(x, y, icon(name, 48).pixmap(48, 48))
