"""Interaction-driven Qt motion. Timelines stop when settled or motion is reduced."""
from PySide6.QtCore import Qt, QVariantAnimation, QEasingCurve, QRectF, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import QPushButton, QWidget, QStylePainter, QStyleOptionButton, QStyle, QGraphicsEffect


def enabled(widget):
    settings = getattr(widget.window(), "settings", None)
    return not (settings and settings.data.get("reduced_motion", False))


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


class MotionButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.hover = self.press = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.pressed.connect(lambda: self.animate_press(1.0))
        self.released.connect(lambda: self.animate_press(0.0))

    def animate_press(self, target):
        tween(self, "_press", self.press, target, self.set_press, 140 if target else 280,
              QEasingCurve.OutCubic if target else QEasingCurve.OutBack)

    def set_press(self, value):
        self.press = float(value)
        self.update()

    def set_hover(self, value):
        self.hover = float(value)
        self.update()

    def enterEvent(self, event):
        tween(self, "_hover", self.hover, 1.0, self.set_hover, 220)
        super().enterEvent(event)

    def leaveEvent(self, event):
        tween(self, "_hover", self.hover, 0.0, self.set_hover, 260)
        super().leaveEvent(event)

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        p = QStylePainter(self)
        scale = 1 - .035 * self.press
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(scale, scale)
        p.translate(-self.width() / 2, -self.height() / 2)
        if not option.icon.isNull():
            size = self.iconSize()
            option.iconSize = QSize(int(size.width() * (1 + .12 * self.hover)), int(size.height() * (1 + .12 * self.hover)))
        p.drawControl(QStyle.CE_PushButton, option)
        if self.hover > .01 and self.isEnabled():
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor(255, 230, 255, int(14 * self.hover)))
            p.setPen(QPen(QColor(244, 185, 255, int(110 * self.hover)), 1.2))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 11, 11)


class MotionIcon(QWidget):
    def __init__(self, name, size=100):
        super().__init__()
        self.name, self.hover, self.reveal = name, 0.0, 1.0
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_hover(self, value):
        self.hover = float(value)
        self.update()

    def engage(self, target):
        tween(self, "_hover", self.hover, target, self.set_hover, 480, QEasingCurve.OutBack)

    def appear(self, delay=0):
        if not enabled(self):
            self.reveal = 1.0
            self.update()
            return
        self.reveal = 0.0
        self.update()
        QTimer.singleShot(delay, self, lambda: tween(self, "_reveal", 0.0, 1.0, self.set_reveal, 600, QEasingCurve.OutBack))

    def set_reveal(self, value):
        self.reveal = float(value)
        self.update()

    def paintEvent(self, event):
        from .design import icon
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        p.setOpacity(min(1, self.reveal))
        p.translate(w / 2, h / 2 + (1 - self.reveal) * 25 - self.hover * 5)
        p.rotate(-4 * self.hover + (1 - self.reveal) * 8)
        p.scale(.8 + .2 * self.reveal + .06 * self.hover, .8 + .2 * self.reveal + .06 * self.hover)
        p.drawPixmap(-w // 2, -h // 2, icon(self.name, w).pixmap(w, h))


class PageEffect(QGraphicsEffect):
    def __init__(self, widget):
        super().__init__(widget)
        self.amount = 0.0

    def advance(self, value):
        self.amount = float(value)
        self.update()

    def draw(self, painter):
        painter.save()
        painter.setOpacity(.15 + .85 * self.amount)
        painter.translate(0, 22 * (1 - self.amount))
        self.drawSource(painter)
        painter.restore()


def reveal_page(widget):
    old = getattr(widget, "_page_motion", None)
    if old:
        old.stop()
    widget.setGraphicsEffect(None)
    if not enabled(widget):
        return
    parent = widget.parentWidget()
    while parent:
        if parent.graphicsEffect():
            return
        parent = parent.parentWidget()
    effect = PageEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = tween(widget, "_page_motion", 0.0, 1.0, effect.advance, 340)
    if animation:
        animation.finished.connect(lambda: widget.setGraphicsEffect(None) if widget.graphicsEffect() is effect else None)


class OrbButton(MotionButton):
    """A bright circular action with an honest task-driven progress ring."""
    def __init__(self, text="Explore", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(84, 84)
        self.setAccessibleName("Explore projects")
        self.busy, self.angle = False, 0.0
        self.spin = QVariantAnimation(self)
        self.spin.setStartValue(0.0)
        self.spin.setEndValue(360.0)
        self.spin.setDuration(1600)
        self.spin.setLoopCount(-1)
        self.spin.valueChanged.connect(self.advance_ring)

    def advance_ring(self, value):
        self.angle = float(value)
        self.update()

    def set_busy(self, busy):
        self.busy = busy
        self.setText("Stop" if busy else "Explore")
        self.setAccessibleName("Cancel current operation" if busy else "Explore projects")
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

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(42, 42)
        scale = 1 + .055 * self.hover - .06 * self.press
        p.scale(scale, scale)
        glow = QRadialGradient(0, 0, 41)
        glow.setColorAt(0, QColor(237, 56, 233, 95))
        glow.setColorAt(1, QColor(237, 56, 233, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(-41, -41, 82, 82))
        body = QLinearGradient(-20, -35, 20, 35)
        body.setColorAt(0, QColor("#eb68ed"))
        body.setColorAt(.45, QColor("#b831d1"))
        body.setColorAt(1, QColor("#7625a5"))
        p.setBrush(body)
        p.setPen(QPen(QColor("#f3c4fb"), 1.2))
        p.drawEllipse(QRectF(-34, -34, 68, 68))
        if self.busy:
            p.setPen(QPen(QColor("#fff4ff"), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(-36, -36, 72, 72), int(self.angle * 16), 100 * 16)
        if self.hasFocus():
            p.setPen(QPen(QColor("#ffffff"), 2, Qt.DotLine))
            p.drawEllipse(QRectF(-39, -39, 78, 78))
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(-34, -20, 68, 40), Qt.AlignCenter, self.text())
