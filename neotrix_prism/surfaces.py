"""Static, resolution-independent gradient surfaces; no repaint timer or blur layers."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QRadialGradient, QPainterPath, QPen
from PySide6.QtWidgets import QWidget, QFrame


class Atmosphere(QWidget):
    dark = False

    def paintEvent(self, event):
        p = QPainter(self)
        base = QLinearGradient(0, 0, self.width(), self.height())
        stops = [(0, "#241339"), (.45, "#19172e"), (1, "#10192b")] if self.dark else [(0, "#eedcf8"), (.45, "#efebfa"), (1, "#e3eafa")]
        for position, color in stops:
            base.setColorAt(position, QColor(color))
        p.fillRect(self.rect(), base)
        glow = QRadialGradient(self.width() * .8, self.height() * .15, self.width() * .7)
        glow.setColorAt(0, QColor(159, 89, 227, 50 if self.dark else 35))
        glow.setColorAt(1, QColor(159, 89, 227, 0))
        p.fillRect(self.rect(), glow)


class GradientTile(QFrame):
    """A painted gradient stays crisp at every Windows display scale."""
    TONES = {"hero": ("#8030ac", "#151344", "#d660de"),
             "Projects": ("#6440a4", "#332463", "#efb375"),
             "Workflows": ("#5143a4", "#24275d", "#54ccea"),
             "Favorites": ("#833b9e", "#392066", "#f885c1")}

    def __init__(self, tone="hero"):
        super().__init__()
        self.tone = tone
        self.setObjectName("hero" if tone == "hero" else "featureTile")
        self.setAttribute(Qt.WA_StyledBackground, False)

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
        glow = QRadialGradient(rect.width() * .92, rect.height() * .08, rect.width() * .63)
        glow.setColorAt(0, QColor(bloom))
        glow.setColorAt(.32, QColor(bloom).lighter(105))
        glow.setColorAt(1, QColor(100, 45, 150, 0))
        p.setOpacity(.28 if self.tone == "hero" else .48)
        p.fillPath(path, glow)
        p.setOpacity(1)
        sheen = QLinearGradient(0, 0, 0, rect.height())
        sheen.setColorAt(0, QColor(255, 255, 255, 38))
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
