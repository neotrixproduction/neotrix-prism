"""Long file lists scroll on springs: no jumps, elastic ends, and they keep their place on refresh."""
import pytest
from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from neotrix_prism.project_browser import FileList

APPS = ['Blender', 'Photoshop', 'After Effects', 'Fusion', 'Illustrator']


def entries(count, order=1):
    rows = [{'path': f'C:/p/f{i}.blend', 'name': f'SH{i % 90:03d}_v{i % 40:03d}.blend', 'relative': f'03/f{i}.blend',
             'application': APPS[i % 5], 'shot': f'SH{i % 90:03d}', 'version': f'v{i % 40:03d}', 'modified': 1.76e9,
             'size': 1000, 'department': 'Lighting', 'kind': 'working'} for i in range(count)]
    return rows[::order]


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setenv('NEOTRIX_USER_DIR', str(tmp_path/'prefs'))
    QApplication.instance() or QApplication([])
    view = FileList()
    view.resize(900, 700)
    view.show()
    view.set_entries(entries(1500))
    QTest.qWait(50)
    yield view
    view.close()


def wheel(view, delta):
    pos = QPointF(450, 350)
    event = QWheelEvent(pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())), QPoint(), QPoint(0, delta),
                        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QCoreApplication.sendEvent(view.viewport(), event)


def test_a_wheel_notch_glides_instead_of_jumping(files):
    bar = files.verticalScrollBar()
    wheel(files, -120)
    QTest.qWait(20)
    assert 0 <= bar.value() < 60  # still on its way, not teleported
    QTest.qWait(700)
    assert bar.value() == pytest.approx(files.STEP, abs=1)


def test_scrolling_past_the_top_stretches_then_eases_home(files):
    for _ in range(3):
        wheel(files, 120)
        QTest.qWait(30)
    QTest.qWait(120)
    assert files.overscroll > 1  # the rows give a little past the end
    QTest.qWait(1200)
    assert files.verticalScrollBar().value() == 0 and abs(files.overscroll) < .01


def test_far_jumps_dissolve_and_land_exactly(files):
    files.setFocus()
    QTest.keyClick(files, Qt.Key_End)
    QTest.qWait(40)
    assert files.warp > 0 and files.warp_ghost is not None
    QTest.qWait(1200)
    bar = files.verticalScrollBar()
    assert bar.value() == bar.maximum() and files.warp_ghost is None


def test_a_refreshed_view_keeps_its_place_but_a_new_order_starts_at_the_top(files):
    bar = files.verticalScrollBar()
    bar.setValue(4500)
    top = files.indexAt(QPoint(12, 12)).row()
    files.set_entries(entries(1505))  # a rescan found five more files
    assert files.indexAt(QPoint(12, 12)).row() == top
    files.set_entries(entries(1505, -1))  # another sort order is another view
    assert bar.value() == 0
