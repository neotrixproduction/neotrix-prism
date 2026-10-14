"""Rounded Windows shell with accessible controls and pointer drag/resize handling."""
from PySide6.QtCore import Qt, QRectF, QEvent, QObject, QRect
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from .motion import MotionButton


class RoundedShell(QWidget):
    def paintEvent(self, event):
        if self.window().isMaximized():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for spread in range(8, 0, -1):
            p.setBrush(QColor(8, 2, 24, 5 + (8 - spread) * 2))
            rect = QRectF(self.rect()).adjusted(8 - spread, 11 - spread, -8 + spread, -5 + spread)
            p.drawRoundedRect(rect, 26 + spread, 26 + spread)


class Caption(QWidget):
    def __init__(self, window):
        super().__init__()
        self.host = window
        self.drag_offset = None
        self.max_drag = False
        self.setObjectName("caption")
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 6, 18, 2)
        layout.setSpacing(9)
        self.title = QLabel("Neotrix Prism")
        self.title.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.title.setStyleSheet("color:#e6d3f4;font-size:12px;background:transparent;")
        self.title.setAlignment(Qt.AlignCenter)
        self.collapse = MotionButton("›")
        self.collapse.setFixedSize(26, 24)
        self.collapse.setStyleSheet("QPushButton {padding:0;border:1px solid rgba(255,255,255,30);border-radius:8px;background:rgba(255,255,255,12);font-size:19px;}")
        self.collapse.setAccessibleName("Collapse or expand navigation")
        self.collapse.setToolTip("Collapse or expand navigation")
        self.collapse.clicked.connect(window.toggle_sidebar)
        # Equal side slots keep the title centered while controls sit at right.
        navigation_slot = QWidget()
        navigation_slot.setFixedWidth(63)
        navigation_layout = QHBoxLayout(navigation_slot)
        navigation_layout.setContentsMargins(0, 0, 0, 0)
        navigation_layout.addWidget(self.collapse)
        navigation_layout.addStretch()
        layout.addWidget(navigation_slot)
        layout.addWidget(self.title, 1)
        controls = QWidget()
        controls.setFixedWidth(63)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(9)
        for name, color, callback, identifier in (
                ("Minimize window", "#ffc35b", window.showMinimized, "windowMinimize"),
                ("Maximize or restore window", "#5ad678", self.toggle_maximize, "windowMaximize"),
                ("Close window", "#ff646b", window.close, "windowClose")):
            control = MotionButton({'windowMinimize':'−', 'windowMaximize':'+', 'windowClose':'×'}[identifier])
            control.setObjectName(identifier)
            control.setFixedSize(15, 15)
            control.setAccessibleName(name)
            control.setToolTip(name)
            control.setStyleSheet("QPushButton {background:" + color + ";color:rgba(20,12,28,220);font-size:12px;font-weight:600;border:1px solid rgba(255,255,255,65);border-radius:7px;padding:0;} QPushButton:focus {border:2px solid white;}")
            control.clicked.connect(callback)
            controls_layout.addWidget(control)
        layout.addWidget(controls)

    def toggle_maximize(self):
        self.host.showNormal() if self.host.isMaximized() else self.host.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.max_drag = self.host.isMaximized()
            self.drag_start = event.globalPosition().toPoint()
            self.drag_fraction = self.host.mapFromGlobal(self.drag_start).x() / max(1, self.host.width())
            self.drag_offset = self.drag_start - self.host.pos()
            self.move_result = "pointer drag"
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.LeftButton:
            if self.max_drag:
                if (event.globalPosition().toPoint() - self.drag_start).manhattanLength() < 8:
                    return
                self.host.showNormal()
                self.drag_offset.setX(int(self.host.width() * self.drag_fraction))
                self.drag_offset.setY(20)
                self.max_drag = False
            self.host.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_offset = None
        self.max_drag = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = None
            self.max_drag = False
            self.toggle_maximize()
            event.accept()


class ResizeFrame(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.host = window
        self.drag_edges = None
        window.centralWidget().setMouseTracking(True)
        window.centralWidget().installEventFilter(self)

    def edges_at(self, point):
        if self.host.isMaximized():
            return Qt.Edges()
        edges = Qt.Edges()
        if point.x() < 8:
            edges |= Qt.LeftEdge
        elif point.x() >= self.host.width() - 8:
            edges |= Qt.RightEdge
        if point.y() < 8:
            edges |= Qt.TopEdge
        elif point.y() >= self.host.height() - 8:
            edges |= Qt.BottomEdge
        return edges

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonRelease and self.drag_edges:
            self.drag_edges = None
            obj.releaseMouse()
            return True
        if event.type() in (QEvent.MouseMove, QEvent.MouseButtonPress):
            if event.type() == QEvent.MouseMove and self.drag_edges:
                delta = event.globalPosition().toPoint() - self.drag_start
                rect = QRect(self.original)
                if self.drag_edges & Qt.LeftEdge:
                    rect.setLeft(min(rect.left()+delta.x(), rect.right()-self.host.minimumWidth()+1))
                if self.drag_edges & Qt.RightEdge:
                    rect.setRight(max(rect.right()+delta.x(), rect.left()+self.host.minimumWidth()-1))
                if self.drag_edges & Qt.TopEdge:
                    rect.setTop(min(rect.top()+delta.y(), rect.bottom()-self.host.minimumHeight()+1))
                if self.drag_edges & Qt.BottomEdge:
                    rect.setBottom(max(rect.bottom()+delta.y(), rect.top()+self.host.minimumHeight()-1))
                self.host.setGeometry(rect)
                return True
            edges = self.edges_at(self.host.mapFromGlobal(event.globalPosition().toPoint()))
            if event.type() == QEvent.MouseMove:
                horizontal = bool(edges & (Qt.LeftEdge | Qt.RightEdge))
                vertical = bool(edges & (Qt.TopEdge | Qt.BottomEdge))
                if horizontal and vertical:
                    same = bool(edges & Qt.LeftEdge) == bool(edges & Qt.TopEdge)
                    obj.setCursor(Qt.SizeFDiagCursor if same else Qt.SizeBDiagCursor)
                else:
                    obj.setCursor(Qt.SizeHorCursor if horizontal else Qt.SizeVerCursor if vertical else Qt.ArrowCursor)
            elif edges and event.button() == Qt.LeftButton:
                self.drag_edges = edges
                self.drag_start = event.globalPosition().toPoint()
                self.original = self.host.geometry()
                self.resize_result = "pointer resize"
                obj.grabMouse()
                return True
        return super().eventFilter(obj, event)
