"""Regression coverage for square clipping of the Refresh/Stop hover artwork."""
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from neotrix_prism.motion import OrbButton


@pytest.mark.parametrize('dpr', [1.0, 1.5, 2.0])
@pytest.mark.parametrize('busy', [False, True])
def test_orb_hover_overshoot_has_transparent_edges(dpr, busy):
    app = QApplication.instance() or QApplication([])
    orb = OrbButton()
    orb.set_busy(busy)
    orb.spin.stop()
    # Include simultaneous hover, landing, and busy spring overshoot, rather
    # than only the smaller resting body. Freeze values for deterministic paint.
    orb.hover, orb.pop, orb.activity = 1.2, 1.2, 1.2 if busy else 0.0
    orb.reveal, orb.swap, orb.angle = 1.0, 1.0, 135.0
    image = QImage(round(orb.width()*dpr), round(orb.height()*dpr),
                   QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    orb.render(painter, QPoint(), renderFlags=QWidget.DrawChildren)
    painter.end()
    width, height = image.width(), image.height()
    edges = [(x, y) for x in range(width) for y in (0, height-1)]
    edges += [(x, y) for y in range(height) for x in (0, width-1)]
    assert max(image.pixelColor(x, y).alpha() for x, y in edges) == 0
    assert image.pixelColor(width//2, height//2).alpha() > 0
    # The original 84 px canvas cut through these pixels on hover.
    y = round((orb.height()/2-43)*dpr)
    assert max(image.pixelColor(x, y).alpha() for x in range(width)) > 0
    orb.close()
    app.processEvents()
