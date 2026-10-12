"""Native Qt graph editor with draggable typed ports and a node inspector."""
import copy
import json
import uuid
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QGraphicsView,
    QGraphicsScene, QGraphicsObject, QGraphicsPathItem, QGraphicsItem, QSplitter, QFormLayout, QLineEdit,
    QLabel, QMessageBox, QFileDialog, QListWidget)
from .graph import NODES, example_graph, validate
from .storage import GraphLibrary, atomic_json
from .motion import MotionButton, tween

PORT_COLORS = {"project": "#ba91e5", "files": "#6caceb", "path": "#61bba6"}


class NodeItem(QGraphicsObject):
    def __init__(self, node, editor):
        super().__init__()
        self.node, self.editor, self.state = node, editor, "ready"
        self.glow = 0.0
        self.setAcceptHoverEvents(True)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setPos(*node.get("position", [60, 60]))
        self.setToolTip(node["type"] + "\nDrag a colored output port to a matching input. Double-click to edit properties.")

    def boundingRect(self):
        return QRectF(0, 0, 205, 116)

    def window(self):
        return self.editor.window()

    def set_glow(self, value):
        self.glow = float(value)
        self.update()

    def hoverEnterEvent(self, event):
        tween(self, "_glow", self.glow, 1.0, self.set_glow, 220)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        tween(self, "_glow", self.glow, 0.0, self.set_glow, 300)
        super().hoverLeaveEvent(event)

    def ports(self, direction):
        return list(NODES[self.node["type"]][direction])

    def port_pos(self, port, direction):
        return QPointF(0 if direction == "inputs" else 205, 69 + 25 * self.ports(direction).index(port))

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        surface = QLinearGradient(0, 0, 205, 116)
        surface.setColorAt(0, QColor("#41314f" if self.editor.dark else "#79509d"))
        surface.setColorAt(1, QColor("#25253d" if self.editor.dark else "#422775"))
        painter.setBrush(QBrush(surface))
        painter.setPen(QPen(QColor("#e1adff" if self.isSelected() else "#9673b4"), 2 if self.isSelected() else 1))
        painter.drawRoundedRect(self.boundingRect().adjusted(1, 1, -1, -1), 15, 15)
        if self.glow:
            painter.setBrush(QColor(214, 162, 255, int(24 * self.glow)))
            painter.setPen(QPen(QColor(232, 181, 255, int(160 * self.glow)), 1.5))
            painter.drawRoundedRect(self.boundingRect().adjusted(2, 2, -2, -2), 14, 14)
        painter.setPen(QColor("#fff5ff"))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(16, 14, 175, 26), self.node["type"])
        colors = {"running": "#e6ab53", "complete": "#56b499", "error": "#df7793", "skipped": "#9b96b1", "ready": "#ada3c4"}
        painter.setBrush(QColor(colors.get(self.state, "#ada3c4")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(185, 28), 4, 4)
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        for direction in ("inputs", "outputs"):
            for port, kind in NODES[self.node["type"]][direction].items():
                point = self.port_pos(port, direction)
                painter.setBrush(QColor(PORT_COLORS[kind]))
                painter.drawEllipse(point, 6, 6)
                painter.setPen(QColor("#cbb5dd" if self.editor.dark else "#e5d0f4"))
                painter.drawText(QRectF(14, point.y() - 9, 178, 20),
                                 Qt.AlignLeft if direction == "inputs" else Qt.AlignRight, port)
                painter.setPen(Qt.NoPen)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.node["position"] = [value.x(), value.y()]
            self.editor.refresh_edges()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.editor.inspect(self.node)
        event.accept()

    def keyPressEvent(self, event):
        moves = {Qt.Key_Left: (-10, 0), Qt.Key_Right: (10, 0), Qt.Key_Up: (0, -10), Qt.Key_Down: (0, 10)}
        if event.key() in moves and self.editor.editable:
            dx, dy = moves[event.key()]
            self.setPos(self.pos() + QPointF(dx, dy))
            event.accept()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.editor.inspect(self.node)
            event.accept()
        else:
            super().keyPressEvent(event)


class GraphView(QGraphicsView):
    def __init__(self, editor):
        super().__init__()
        self.editor, self.start_port, self.rubber = editor, None, None
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setSceneRect(-500, -500, 2400, 1500)

    def wheelEvent(self, event):
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        scale = self.transform().m11() * factor
        if .25 < scale < 2.5:
            self.scale(factor, factor)
        event.accept()

    def port_at(self, position, direction):
        scene_point = self.mapToScene(position)
        for item in self.editor.items.values():
            for port in item.ports(direction):
                point = item.mapToScene(item.port_pos(port, direction))
                if (point - scene_point).manhattanLength() < 16:
                    return item, port
        return None

    def mousePressEvent(self, event):
        if not self.editor.editable:
            return super().mousePressEvent(event)
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            from PySide6.QtGui import QMouseEvent
            fake = QMouseEvent(event.type(), event.position(), Qt.LeftButton, Qt.LeftButton, event.modifiers())
            super().mousePressEvent(fake)
            return
        self.start_port = self.port_at(event.position().toPoint(), "outputs")
        if self.start_port:
            self.rubber = QGraphicsPathItem()
            self.rubber.setPen(QPen(QColor("#9b8bea"), 2))
            self.scene().addItem(self.rubber)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start_port:
            item, port = self.start_port
            start = item.mapToScene(item.port_pos(port, "outputs"))
            self.rubber.setPath(curve(start, self.mapToScene(event.position().toPoint())))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start_port:
            target = self.port_at(event.position().toPoint(), "inputs")
            if target:
                self.editor.connect_ports(self.start_port, target)
            self.scene().removeItem(self.rubber)
            self.start_port, self.rubber = None, None
            event.accept()
        elif event.button() == Qt.MiddleButton:
            from PySide6.QtGui import QMouseEvent
            super().mouseReleaseEvent(QMouseEvent(event.type(), event.position(), Qt.LeftButton, Qt.NoButton, event.modifiers()))
            self.setDragMode(QGraphicsView.RubberBandDrag)
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.editor.editable:
            self.editor.remove_selected()
        else:
            super().keyPressEvent(event)

    def drawBackground(self, painter, rect):
        background = QLinearGradient(rect.topLeft(), rect.bottomRight())
        background.setColorAt(0, QColor("#241e35" if self.editor.dark else "#4c267c"))
        background.setColorAt(1, QColor("#161e30" if self.editor.dark else "#291b57"))
        painter.fillRect(rect, background)
        painter.setPen(QPen(QColor("#36374e" if self.editor.dark else "#6b4392"), 1))
        start_x, start_y = int(rect.left()) // 24 * 24, int(rect.top()) // 24 * 24
        for x in range(start_x, int(rect.right()), 24):
            for y in range(start_y, int(rect.bottom()), 24):
                painter.drawPoint(x, y)


def curve(start, end):
    path = QPainterPath(start)
    distance = max(60, abs(end.x() - start.x()) / 2)
    path.cubicTo(start + QPointF(distance, 0), end - QPointF(distance, 0), end)
    return path


class GraphEditor(QWidget):
    preview_requested = Signal(dict)

    def __init__(self, root, dark=False):
        super().__init__()
        self.library = GraphLibrary(root)
        self.dark, self.editable = dark, True
        self.graph, self.filename, self.expected = example_graph(), None, None
        self.items, self.edges = {}, []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.name = QLineEdit(self.graph["name"])
        self.name.setPlaceholderText("Workflow name")
        toolbar.addWidget(self.name, 1)
        self.kind = QComboBox()
        self.kind.addItems(NODES)
        toolbar.addWidget(self.kind)
        layout.addLayout(toolbar)
        toolbar = QHBoxLayout()
        self.mutation_buttons = []
        for title, callback in (("New", self.new_graph), ("Add node", self.add_node), ("Remove", self.remove_selected), ("Save", self.save), ("Save as", self.save_as),
                                ("Import", self.import_graph), ("Export", self.export_graph), ("Fit", self.fit)):
            button = MotionButton(title)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
            if title not in ("Fit", "Export"):
                self.mutation_buttons.append(button)
        layout.addLayout(toolbar)
        toolbar.addStretch()
        split = QSplitter()
        self.view = GraphView(self)
        split.addWidget(self.view)
        side = QWidget()
        side.setMinimumWidth(205)
        side.setMaximumWidth(250)
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("Shared workflows"))
        self.library_list = QListWidget()
        self.library_list.itemDoubleClicked.connect(self.load_item)
        side_layout.addWidget(self.library_list)
        refresh = MotionButton("Refresh library")
        refresh.clicked.connect(self.refresh_library)
        side_layout.addWidget(refresh)
        side_layout.addWidget(QLabel("Node properties"))
        self.inspector = QWidget()
        self.form = QFormLayout(self.inspector)
        side_layout.addWidget(self.inspector)
        self.hint = QLabel("Drag matching colored ports to connect.\nDouble-click a node to edit.\nScroll to zoom • middle-drag to pan.")
        self.hint.setWordWrap(True)
        side_layout.addWidget(self.hint)
        self.run_button = MotionButton("Preview workflow")
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(self.request_preview)
        side_layout.addWidget(self.run_button)
        split.addWidget(side)
        split.setStretchFactor(0, 1)
        layout.addWidget(split, 1)
        self.refresh_library()
        self.render()

    def render(self):
        self.view.scene().clear()
        self.items, self.edges = {}, []
        for node in self.graph["nodes"]:
            item = NodeItem(node, self)
            item.setFlag(QGraphicsItem.ItemIsMovable, self.editable)
            self.items[node["id"]] = item
            self.view.scene().addItem(item)
        self.refresh_edges()
        self.fit()

    def refresh_edges(self):
        for item in self.edges:
            if item.scene():
                self.view.scene().removeItem(item)
        self.edges = []
        for edge in self.graph["edges"]:
            source, target = self.items.get(edge["source"]), self.items.get(edge["target"])
            if not source or not target:
                continue
            line = QGraphicsPathItem(curve(source.mapToScene(source.port_pos(edge["output"], "outputs")),
                                          target.mapToScene(target.port_pos(edge["input"], "inputs"))))
            line.setPen(QPen(QColor(PORT_COLORS[NODES[source.node["type"]]["outputs"][edge["output"]]]), 2.2))
            line.setZValue(-1)
            self.view.scene().addItem(line)
            self.edges.append(line)

    def fit(self):
        if self.items:
            rect = self.view.scene().itemsBoundingRect().adjusted(-50, -50, 50, 50)
            self.view.fitInView(rect, Qt.KeepAspectRatio)

    def add_node(self):
        kind = self.kind.currentText()
        center = self.view.mapToScene(self.view.viewport().rect().center())
        node = {"id": uuid.uuid4().hex[:12], "type": kind, "position": [center.x(), center.y()], "props": dict(NODES[kind]["props"])}
        self.graph["nodes"].append(node)
        item = NodeItem(node, self)
        self.items[node["id"]] = item
        self.view.scene().addItem(item)
        self.inspect(node)

    def new_graph(self):
        self.graph = {"format": 1, "name": "New workflow", "revision": 0, "nodes": [
            {"id": uuid.uuid4().hex[:12], "type": "Project Input", "position": [60, 100], "props": {}}], "edges": []}
        self.filename, self.expected = None, None
        self.name.setText(self.graph["name"])
        self.clear_form()
        self.render()

    def save_as(self):
        self.filename, self.expected = None, None
        self.save()

    def remove_selected(self):
        selected = {i.node["id"] for i in self.view.scene().selectedItems() if isinstance(i, NodeItem)}
        self.graph["nodes"] = [n for n in self.graph["nodes"] if n["id"] not in selected]
        self.graph["edges"] = [e for e in self.graph["edges"] if e["source"] not in selected and e["target"] not in selected]
        self.clear_form()
        self.render()

    def connect_ports(self, source, target):
        source_item, output = source
        target_item, inp = target
        kind_out = NODES[source_item.node["type"]]["outputs"][output]
        kind_in = NODES[target_item.node["type"]]["inputs"][inp]
        if source_item is target_item or kind_out != kind_in:
            QMessageBox.warning(self, "Connection", "Connect different nodes with matching port colors.")
            return
        edge = {"source": source_item.node["id"], "output": output, "target": target_item.node["id"], "input": inp}
        self.graph["edges"] = [e for e in self.graph["edges"] if (e["target"], e["input"]) != (edge["target"], edge["input"])]
        self.graph["edges"].append(edge)
        self.refresh_edges()

    def clear_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)

    def inspect(self, node):
        self.clear_form()
        self.form.addRow(QLabel(node["type"]))
        for key, default in NODES[node["type"]]["props"].items():
            if key == "application":
                field = QComboBox()
                field.addItems(["All", "Blender", "Photoshop", "Illustrator", "After Effects", "Fusion"])
                field.setCurrentText(node["props"].get(key, default))
                field.currentTextChanged.connect(lambda value, k=key: node["props"].update({k: value}))
            else:
                field = QLineEdit(str(node["props"].get(key, default)))
                field.textChanged.connect(lambda value, k=key: node["props"].update({k: value}))
            field.setEnabled(self.editable)
            self.form.addRow(key.capitalize(), field)

    def refresh_library(self):
        try:
            self.records = self.library.list()
            self.editable = self.library.online()
        except OSError:
            from .storage import read_json
            self.records = read_json(self.library.cache, [])
            self.editable = False
        self.library_list.clear()
        for record in self.records:
            self.library_list.addItem(record["graph"].get("name", record["filename"]))
        for button in self.mutation_buttons:
            button.setEnabled(self.editable)
        self.name.setReadOnly(not self.editable)
        self.kind.setEnabled(self.editable)
        self.run_button.setEnabled(self.editable)
        for item in self.items.values():
            item.setFlag(QGraphicsItem.ItemIsMovable, self.editable)
        if not self.editable:
            self.hint.setText("Relay disconnected.\nCached graphs are view-only until storage reconnects.")
        else:
            self.hint.setText("Drag matching colored ports to connect.\nDouble-click a node to edit.\nScroll to zoom • middle-drag to pan.")

    def load_item(self, item):
        record = self.records[self.library_list.row(item)]
        self.graph, self.filename, self.expected = copy.deepcopy(record["graph"]), record["filename"], record["fingerprint"]
        self.name.setText(self.graph["name"])
        self.clear_form()
        self.render()

    def snapshot(self):
        graph = copy.deepcopy(self.graph)
        graph["name"] = self.name.text().strip() or "Untitled workflow"
        validate(graph)
        return graph

    def save(self):
        try:
            graph = self.snapshot()
            import re
            filename = self.filename or re.sub(r"[^a-zA-Z0-9_-]", "-", graph["name"]).strip("-") + ".json"
            graph["revision"] = graph.get("revision", 0) + 1
            self.expected = self.library.save(filename, graph, self.expected)
            self.filename, self.graph = filename, graph
            self.refresh_library()
        except Exception as exc:
            QMessageBox.warning(self, "Workflow save", str(exc))

    def import_graph(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import workflow", "", "Workflow (*.json)")
        if path:
            try:
                graph = json.loads(Path(path).read_text(encoding="utf-8"))
                validate(graph)
                self.graph, self.filename, self.expected = graph, None, None
                self.name.setText(graph.get("name", "Imported workflow"))
                self.clear_form()
                self.render()
            except Exception as exc:
                QMessageBox.warning(self, "Import", str(exc))

    def export_graph(self):
        try:
            graph = self.snapshot()
            path, _ = QFileDialog.getSaveFileName(self, "Export workflow", "workflow.json", "Workflow (*.json)")
            if path:
                atomic_json(path, graph)
        except Exception as exc:
            QMessageBox.warning(self, "Export", str(exc))

    def request_preview(self):
        try:
            self.preview_requested.emit(self.snapshot())
        except Exception as exc:
            QMessageBox.warning(self, "Workflow validation", str(exc))

    def set_node_state(self, identifier, state):
        if identifier in self.items:
            self.items[identifier].state = state
            self.items[identifier].update()
