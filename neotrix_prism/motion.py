"""Interaction-driven Qt motion. Timelines stop when settled or motion is reduced."""
from PySide6.QtCore import Qt, QVariantAnimation, QEasingCurve, QRectF, QSize, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QRadialGradient, QPainterPath
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
        self.ripple = 1.0
        self.ripple_origin = QPointF()
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

    def mousePressEvent(self, event):
        self.ripple_origin = event.position()
        def advance(value):
            self.ripple = float(value)
            self.update()
        tween(self, '_ripple', 0.0, 1.0, advance, 580)
        super().mousePressEvent(event)

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
        if enabled(self) and 0 < self.ripple < 1:
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),11,11)
            p.setClipPath(clip)
            radius = max(self.width(),self.height())*self.ripple
            p.setPen(QPen(QColor(255,230,255,int(130*(1-self.ripple))),1.5))
            p.setBrush(QColor(255,230,255,int(25*(1-self.ripple))))
            p.drawEllipse(self.ripple_origin,radius,radius)


class MotionIcon(QWidget):
    def __init__(self, name, size=100):
        super().__init__()
        self.name, self.hover, self.reveal = name, 0.0, 1.0
        self.pointer = QPointF()
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_hover(self, value):
        self.hover = float(value)
        self.update()

    def engage(self, target):
        tween(self, "_hover", self.hover, target, self.set_hover, 480, QEasingCurve.OutBack)

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
        # Artwork floats independently of the surface: depth comes from the
        # pointer offset, changing shadow and delayed spring settlement.
        import math
        art = int(min(w,h)*.76)
        angle = -11*self.hover + self.pointer.x()*7*self.hover + (1-self.reveal)*24
        footprint = abs(math.cos(math.radians(angle)))+abs(math.sin(math.radians(angle)))
        sx = min(.55+.45*self.reveal+.16*self.hover,(w-4)/(art*footprint))
        sy = min(.55+.45*self.reveal+.12*self.hover,(h-4)/(art*footprint))
        extent = art*max(sx,sy)*footprint/2+1
        x = max(extent,min(w-extent,w/2+self.pointer.x()*10*self.hover))
        y = max(extent,min(h-extent,h/2+(1-self.reveal)*58-self.hover*13+self.pointer.y()*8*self.hover))
        p.translate(x,y)
        shadow = QRadialGradient(0, h * .32, w * .48)
        shadow.setColorAt(0, QColor(10, 5, 36, int(95 * self.hover)))
        shadow.setColorAt(1, QColor(10, 5, 36, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(shadow)
        p.drawEllipse(QRectF(-w*.48, h*.15, w*.96, h*.3))
        p.rotate(angle)
        p.scale(sx,sy)
        # Keep a safe apron for spring rotation, lift and pointer parallax.
        # Painting the artwork edge-to-edge clipped it inside its QWidget.
        p.drawPixmap(-art // 2, -art // 2, icon(self.name, art).pixmap(art, art))


class PageEffect(QGraphicsEffect):
    def __init__(self, widget):
        super().__init__(widget)
        self.amount = 0.0

    def advance(self, value):
        self.amount = float(value)
        self.update()

    def draw(self, painter):
        painter.save()
        painter.setOpacity(max(0, min(1, self.amount)))
        rect = self.sourceBoundingRect()
        painter.translate(rect.width()/2, rect.height()/2 + 54 * (1 - self.amount))
        painter.scale(.9 + .1*self.amount, .9 + .1*self.amount)
        painter.translate(-rect.width()/2, -rect.height()/2)
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


class SceneTransition(QWidget):
    """A short-lived snapshot layer; real controls remain live underneath.

    Tile navigation grows from its actual source rectangle. Sidebar navigation
    uses directional depth. Interrupted transitions release both pixmaps.
    """
    def __init__(self, stack, outgoing, origin=None, direction=1):
        super().__init__(stack)
        self.outgoing, self.incoming = outgoing, stack.currentWidget().grab()
        self.amount = 0.0
        self.origin = QRectF(origin) if origin else None
        self.direction = direction
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(stack.rect())
        self.show()
        self.raise_()
        animation = tween(self, '_scene', 0.0, 1.0, self.advance, 420, QEasingCurve.InOutCubic)
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
        self.outgoing = self.incoming = None
        self.deleteLater()

    def paintEvent(self, event):
        if self.incoming is None:
            return
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        full, t = QRectF(self.rect()), self.amount
        boundary=QPainterPath()
        boundary.addRoundedRect(full,22,22)
        p.setClipPath(boundary)
        # Opaque underlay prevents the final live page peeking through early.
        p.fillRect(full, QColor('#35205d'))
        if self.outgoing and not self.outgoing.isNull():
            p.save()
            p.setOpacity(1 if self.origin else max(0,1-t*2))
            old = full if self.origin else full.adjusted(t*36, t*20, -t*36, -t*20)
            if not self.origin:
                old.translate(-self.direction*t*90, 0)
            p.drawPixmap(old, self.outgoing, QRectF(self.outgoing.rect()))
            p.restore()
        if self.origin:
            start = self.origin
            target = QRectF(start.x()*(1-t), start.y()*(1-t),
                            start.width()+(full.width()-start.width())*t,
                            start.height()+(full.height()-start.height())*t)
        else:
            target = full.adjusted((1-t)*28, (1-t)*18, -(1-t)*28, -(1-t)*18)
            target.translate(self.direction*(1-t)*110, 0)
        path = QPainterPath()
        path.addRoundedRect(target, 26*(1-t), 26*(1-t))
        p.setClipPath(path,Qt.IntersectClip)
        p.setOpacity(1 if self.origin else min(1, t*2))
        # Reveal live-size content through the growing container, rather than
        # stretching small text and cross-fading two dense interfaces.
        p.drawPixmap(full if self.origin else target, self.incoming, QRectF(self.incoming.rect()))


class OrbButton(MotionButton):
    """A bright circular action with an honest task-driven progress ring."""
    def __init__(self, text="Explore", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(84, 84)
        self.setAccessibleName("Explore projects")
        self.busy, self.angle = False, 0.0
        self.activity = 0.0
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
        changed = self.busy != busy
        self.busy = busy
        if changed:
            def advance(value):
                self.activity = float(value)
                self.update()
            tween(self, '_activity', self.activity, 1.0 if busy else 0.0, advance, 520, QEasingCurve.OutBack)
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
        scale = 1 + .10 * self.hover - .09 * self.press + .035*self.activity
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
        highlight = QRadialGradient(-14-self.hover*8,-22,40)
        highlight.setColorAt(0,QColor(255,255,255,int(80+40*self.hover)))
        highlight.setColorAt(.5,QColor(255,220,255,15))
        highlight.setColorAt(1,QColor(255,255,255,0))
        p.setPen(Qt.NoPen)
        p.setBrush(highlight)
        p.drawEllipse(QRectF(-33,-33,66,66))
        if self.busy:
            import math
            p.setPen(QPen(QColor("#fff4ff"), 3, Qt.SolidLine, Qt.RoundCap))
            span = 100 + 65*math.sin(math.radians(self.angle)) if enabled(self) else 100
            p.drawArc(QRectF(-36, -36, 72, 72), int(self.angle * 16), int(span * 16))
            p.setPen(QPen(QColor(251,177,255,100),1.5,Qt.SolidLine,Qt.RoundCap))
            p.drawArc(QRectF(-39,-39,78,78),int(-self.angle*16),55*16)
        if self.hasFocus():
            p.setPen(QPen(QColor("#ffffff"), 2, Qt.DotLine))
            p.drawEllipse(QRectF(-39, -39, 78, 78))
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(-34, -20, 68, 40), Qt.AlignCenter, self.text())
