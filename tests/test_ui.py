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


def test_rounded_shell_maximize_restore(window):
    window, project, messages, wait = window
    window.workflow_project.setCurrentIndex(window.workflow_project.findData(str(project)))
    assert window.windowFlags() & Qt.FramelessWindowHint
    assert not window.surface.mask().contains(QPoint(0, 0))
    assert window.workflow_project.currentData() == str(project)
    assert window.surface.mask().contains(window.surface.rect().center())
    window.showMaximized()
    QTest.qWait(80)
    assert window.surface.mask().isEmpty()
    window.showNormal()
    QTest.qWait(80)
    assert not window.surface.mask().contains(QPoint(0, 0))
    assert not messages


def test_interrupted_page_motion_and_sidebar(window):
    from PySide6.QtCore import QAbstractAnimation
    window, project, messages, wait = window
    window.settings.data['reduced_motion'] = False
    window.apply_theme()
    window.navigate('Projects')
    window.navigate('Home')
    window.navigate('Settings')
    QTest.qWait(450)
    assert window.stack.currentWidget() is window.pages['Settings']
    assert all(page.graphicsEffect() is None for page in window.pages.values())
    window.toggle_sidebar()
    QTest.qWait(450)
    assert window.sidebar.width() == 78
    assert all(not button.text() and button.toolTip() for button in window.nav.values())
    QTest.mouseClick(window.nav['Workflows'], Qt.LeftButton)
    QTest.qWait(450)
    assert window.stack.currentWidget() is window.pages['Workflows']
    window.toggle_sidebar()
    QTest.qWait(450)
    assert window.sidebar.width() == 202
    assert window.selection_rail.geometry() == window.nav['Workflows'].geometry()
    assert window.orb.spin.state() == QAbstractAnimation.Stopped
    assert not messages


def test_orb_cancels_busy_task_and_stops_motion(window):
    from PySide6.QtCore import QAbstractAnimation
    window, project, messages, wait = window
    window.settings.data['reduced_motion'] = False
    window.navigate('Home')
    job = window.worker(lambda task: task.cancel.wait(3), lambda result: None)
    QTest.qWait(60)
    assert window.orb.spin.state() == QAbstractAnimation.Running
    QTest.mouseClick(window.orb, Qt.LeftButton)
    wait()
    assert job.cancel.is_set()
    assert not window.orb.busy
    assert window.orb.spin.state() == QAbstractAnimation.Stopped
    window.settings.data['reduced_motion'] = True
    window.apply_theme()
    window.orb.set_busy(True)
    assert window.orb.spin.state() == QAbstractAnimation.Stopped
    assert not window.progress_bar.isVisible()
    window.orb.set_busy(False)
    window.navigate('Home')
    assert window.pages['Home'].graphicsEffect() is None
    assert not messages


def test_caption_drag_and_resize_constraints(window):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    window, project, messages, wait = window
    app = QApplication.instance()
    def send(widget, kind, global_position, button, buttons):
        local = QPointF(widget.mapFromGlobal(global_position))
        event = QMouseEvent(kind, local, QPointF(global_position), button, buttons, Qt.NoModifier)
        app.sendEvent(widget, event)
    before = window.pos()
    start = window.caption.mapToGlobal(QPoint(180, 15))
    send(window.caption, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    send(window.caption, QEvent.MouseMove, start+QPoint(40,20), Qt.NoButton, Qt.LeftButton)
    send(window.caption, QEvent.MouseButtonRelease, start+QPoint(40,20), Qt.LeftButton, Qt.NoButton)
    assert window.pos() == before+QPoint(40,20)
    shell = window.centralWidget()
    start = shell.mapToGlobal(QPoint(shell.width()-4, shell.height()//2))
    send(shell, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    send(shell, QEvent.MouseMove, start-QPoint(900,0), Qt.NoButton, Qt.LeftButton)
    send(shell, QEvent.MouseButtonRelease, start-QPoint(900,0), Qt.LeftButton, Qt.NoButton)
    assert window.width() == window.minimumWidth()
    window.showMaximized()
    QTest.qWait(50)
    start = window.caption.mapToGlobal(QPoint(180,15))
    send(window.caption, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    send(window.caption, QEvent.MouseButtonRelease, start, Qt.LeftButton, Qt.NoButton)
    assert window.isMaximized()  # A single caption click must not restore the window.
    window.showNormal()
    assert not messages


def test_bundled_display_and_text_fonts(window):
    from neotrix_prism.typography import roles
    from PySide6.QtGui import QFontInfo
    window, project, messages, wait = window
    assert roles() == ('Manrope','Manrope')
    assert QFontInfo(window.page_title.font()).family() == 'Manrope'
    assert QFontInfo(window.project_search.font()).family() == 'Manrope'


def test_bento_fits_minimum_window(window):
    from PySide6.QtWidgets import QScrollArea
    window, project, messages, wait = window
    window.resize(1024,720)
    window.navigate('Home')
    QTest.qWait(100)
    scroll = window.pages['Home'].findChild(QScrollArea)
    assert scroll.horizontalScrollBar().maximum() == 0


def test_tile_scene_transition_interrupt_and_reduce(window):
    from neotrix_prism.surfaces import GradientTile
    from neotrix_prism.motion import SceneTransition, MotionButton
    from PySide6.QtCore import QAbstractAnimation, QVariantAnimation
    window, project, messages, wait = window
    window.settings.data['reduced_motion'] = False
    window.navigate('Home')
    QTest.qWait(800)
    tile = next(t for t in window.pages['Home'].findChildren(GradientTile) if t.tone == 'Projects')
    control = next(b for b in tile.findChildren(MotionButton) if b.text() == 'Open projects')
    QTest.mouseClick(control, Qt.LeftButton)
    transition = window._scene_transition
    assert transition.origin is not None
    assert transition.isVisible()
    assert window.stack.currentWidget() is window.pages['Projects']
    window.navigate('Workflows')
    window.navigate('Settings')
    window.settings.data['reduced_motion'] = True
    window.apply_theme()
    QTest.qWait(50)
    assert not any(t.isVisible() for t in window.findChildren(SceneTransition))
    assert all(a.state() == QAbstractAnimation.Stopped for a in window.findChildren(QVariantAnimation))
    assert window.stack.currentWidget() is window.pages['Settings']
    assert not messages


def test_task_orb_position_is_fixed(window):
    window, project, messages, wait = window
    window.settings.data['reduced_motion'] = False
    for size in ((1360,900),(1024,720)):
        window.resize(*size)
        window.navigate('Home')
        QTest.qWait(450)
        anchor = window.orb.mapTo(window, QPoint(42,42))
        window.worker(lambda task: task.cancel.wait(3), lambda result: None)
        window.status.setText('Long operation status with a full creative project path and detailed progress information')
        QTest.qWait(100)
        assert window.orb.mapTo(window,QPoint(42,42)) == anchor
        QTest.mouseClick(window.orb,Qt.LeftButton)
        wait()
        QTest.qWait(100)
        assert window.orb.mapTo(window,QPoint(42,42)) == anchor
    assert not messages
