"""Resolution-independent surfaces with finite, interaction-driven lighting."""
from PySide6.QtCore import QRectF, Qt, QEasingCurve, Signal, QPointF, QEvent, QTimer
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QRadialGradient, QPainterPath, QPen, QRegion
from PySide6.QtWidgets import QWidget, QFrame
from .motion import tween, MotionIcon, enabled


class Atmosphere(QWidget):
    dark = False
    accent = 0.0

    def focus_scene(self, index):
        def step(value):
            self.accent = float(value)
            self.update()
        tween(self,'_atmosphere',self.accent,float(index),step,700,QEasingCurve.InOutCubic)

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

    def paintEvent(self, event):
        p = QPainter(self)
        base = QLinearGradient(0, 0, self.width(), self.height())
        stops = [(0, "#4a1b65"), (.45, "#271447"), (1, "#100f32")] if self.dark else [(0, "#822799"), (.43, "#4b217e"), (1, "#160f48")]
        for position, color in stops:
            base.setColorAt(position, QColor(color))
        p.fillRect(self.rect(), base)
        import math
        glow = QRadialGradient(self.width() * (.3+.24*math.sin(self.accent)),
                               self.height() * (.70+.18*math.cos(self.accent)), self.width() * .65)
        glow.setColorAt(0, QColor(145, 44, 215, 60 if self.dark else 95))
        glow.setColorAt(1, QColor(145, 44, 215, 0))
        p.fillRect(self.rect(), glow)
        sky = QRadialGradient(self.width()*(.72+.12*math.sin(self.accent)),self.height()*.1,self.width()*.55)
        sky.setColorAt(0,QColor(211,87,203,40 if self.dark else 65))
        sky.setColorAt(1,QColor(211,87,203,0))
        p.fillRect(self.rect(),sky)


class GradientTile(QFrame):
    """A painted gradient stays crisp at every Windows display scale."""
    hover_changed = Signal(float)
    TONES = {"hero": ("#8030ac", "#151344", "#d660de"),
             "Projects": ("#6440a4", "#332463", "#efb375"),
             "Workflows": ("#5143a4", "#24275d", "#54ccea"),
             "Favorites": ("#833b9e", "#392066", "#f885c1"),
             "Recent": ("#633693", "#28245f", "#8594ed"),
             "Storage": ("#55378c", "#26225d", "#60d8c8")}

    def __init__(self, tone="hero"):
        super().__init__()
        self.tone = tone
        self.hover = 0.0
        self.pointer = QPointF(.75, .18)
        self.sweep = 1.0
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
        destination = QPointF(point.x()/max(1,self.width()), point.y()/max(1,self.height()))
        def step(value):
            self.pointer = value
            for artwork in self.findChildren(MotionIcon):
                artwork.track(QPointF((value.x()-.5)*2, (value.y()-.5)*2))
            self.update()
        tween(self, '_pointer', self.pointer, destination, step, 180)

    def set_sweep(self, value):
        self.sweep = float(value)
        self.update()

    def set_hover(self, value):
        self.hover = float(value)
        self.update()
        self.hover_changed.emit(self.hover)

    def enterEvent(self, event):
        tween(self, "_hover", self.hover, 1.0, self.set_hover, 520, QEasingCurve.OutBack)
        tween(self, '_sheen', 0.0, 1.0, self.set_sweep, 850, QEasingCurve.InOutCubic)
        for artwork in self.findChildren(MotionIcon):
            artwork.engage(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        tween(self, "_hover", self.hover, 0.0, self.set_hover, 600, QEasingCurve.OutCubic)
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
        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0, QColor(first))
        base.setColorAt(1, QColor(last))
        p.fillPath(path, base)
        glow = QRadialGradient(rect.width() * (.92 - .12 * self.hover), rect.height() * .08, rect.width() * .63)
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
