"""Refresh ripple physics, panel effects, and the quiet footer status/progress."""
import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QLabel
from neotrix_prism import physics
from neotrix_prism.choreo import Hairline, StatusLine
from neotrix_prism.motion import HiddenEffect, RippleLayer, ripple_blocks


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_ripple_pushes_out_rebounds_once_and_settles():
    samples = [physics.ripple(t)[0] for t in range(0, physics.RIPPLE_MS+50, 5)]
    assert max(samples) == pytest.approx(1.0, abs=.01)
    assert samples.index(max(samples))*5 < 200  # the push lands quickly
    assert -.4 < min(samples) < -.2  # a rebound through rest, then a smaller swing
    assert physics.ripple(-10) == (0.0, 0.0) and physics.ripple(physics.RIPPLE_MS) == (0.0, 0.0)


def test_ripple_blocks_ride_a_layer_uncropped_and_clean_up(app):
    host = QWidget()
    host.resize(600, 400)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    container = QWidget()  # zero margins: moving in place would crop at its edge
    inner = QVBoxLayout(container)
    inner.setContentsMargins(0, 0, 0, 0)
    blocks = [QLineEdit('search'), QLabel('breadcrumb')]
    for block in blocks:
        inner.addWidget(block)
    layout.addWidget(container)
    host.show()
    QTest.qWait(20)
    layer = ripple_blocks(host, blocks, QPointF(300, 400))
    assert isinstance(layer, RippleLayer) and layer.parentWidget() is host
    QTest.qWait(250)
    flying = [g for g in layer.ghosts if g['pixmap'] is not None and not g['done']]
    assert flying, 'ghosts should be riding the wave'
    assert all(isinstance(g['block'].graphicsEffect(), HiddenEffect) for g in flying)
    assert any(g['offset'].manhattanLength() > 1 for g in flying)
    assert all(g['clip'] == QRectF(layer.rect()) for g in layer.ghosts)  # not clipped by the container
    ripple_blocks(host, blocks, QPointF(300, 400))  # a second refresh replaces the first cleanly
    QTest.qWait(physics.RIPPLE_MS+700)
    assert all(block.graphicsEffect() is None for block in blocks)
    assert getattr(host, '_ripple_layer', None) is None or not host._ripple_layer.isVisible()
    host.close()


def test_status_line_elides_quietly_with_full_tooltip(app):
    status = StatusLine('Ready')
    status.resize(220, 20)
    status.show()
    long_text = '12,480 files found  ·  ' + 'very long folder name ' * 8
    status.setText(long_text)
    assert status.full == long_text
    assert '…' in QLabel.text(status) and status.toolTip() == long_text
    status.setText('Ready')
    assert QLabel.text(status) == 'Ready' and status.toolTip() == ''
    status.close()


def test_hairline_fades_in_and_out(app):
    line = Hairline()
    line.set_active(True)
    assert line.isVisible() and line.active
    QTest.qWait(400)
    assert line.presence > .9
    line.set_active(False)
    QTest.qWait(1500)
    assert not line.isVisible() and line.presence < .02
    line.close()
