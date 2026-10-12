import os
import time
from pathlib import Path
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
from neotrix_prism.storage import Settings
from neotrix_prism.ui import MainWindow
from neotrix_prism.graph_ui import NodeItem


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("NEOTRIX_USER_DIR", str(tmp_path / "prefs"))
    app = QApplication.instance() or QApplication([])
    root = tmp_path / "share"
    project = root / "Neotrix Demo"
    project.mkdir(parents=True)
    for filename in ("Scene_v001.blend", "Scene_v002.blend", "Poster_v001.psd", "Edit_V0001.aep", "Logo.ai", "Comp.comp"):
        (project / filename).write_bytes(b"QA indexing fixture")
    settings = Settings()
    settings.data.update(roots=[str(root)], graph_root=str(root), reduced_motion=True)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[2]))
    result = MainWindow(settings)
    result.show()
    def wait():
        deadline = time.time() + 15
        while result.jobs and time.time() < deadline:
            app.processEvents()
            QTest.qWait(10)
        assert not result.jobs
    wait()
    yield result, project, messages, wait
    result.close()
    app.processEvents()


def test_navigation_filter_favorite_theme(window):
    window, project, messages, wait = window
    assert window.workflow_project.count() == 2
    window.open_project(str(project))
    wait()
    assert window.file_table.rowCount() == 6
    combo = window.filters["application"]
    combo.setCurrentText("Blender")
    assert window.file_table.rowCount() == 2
    window.file_table.selectRow(0)
    window.favorite_selected()
    window.navigate("Favorites")
    assert window.favorite_table.rowCount() == 1
    window.navigate("Settings")
    window.theme.setCurrentText("dark")
    window.save_settings()
    wait()
    assert window.editor.dark
    assert not messages


def test_graph_canvas_inspector_validation(window):
    window, project, messages, wait = window
    window.navigate("Workflows")
    editor = window.editor
    editor.inspect(editor.graph["nodes"][2])
    assert editor.form.rowCount() == 3
    before = len(editor.graph["nodes"])
    editor.kind.setCurrentText("Open Files")
    editor.add_node()
    assert len(editor.graph["nodes"]) == before + 1
    item = editor.items[editor.graph["nodes"][-1]["id"]]
    item.setSelected(True)
    editor.remove_selected()
    assert len(editor.graph["nodes"]) == before
    start = editor.items["1"].pos()
    editor.items["1"].setPos(start.x() + 30, start.y())
    assert editor.graph["nodes"][1]["position"][0] == start.x() + 30
    assert len(editor.edges) == 7
