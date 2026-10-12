"""Shared Neotrix design tokens, original SVG icons and lightweight animation."""
from PySide6.QtCore import QByteArray, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPalette, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QGraphicsOpacityEffect

COLORS = {"Home": "#8875f0", "Projects": "#efac5c", "Favorites": "#e78caa",
          "Workflows": "#6ca6ee", "Activity": "#55bba5", "Settings": "#a59bc6",
          "Blender": "#ef9e52", "Photoshop": "#59a4e9", "Illustrator": "#d69b44",
          "After Effects": "#9b8ced", "Fusion": "#e07794"}
PATHS = {
    "Home": '<path d="M12 25L32 9l20 16v27H36V36h-8v16H12z"/>',
    "Projects": '<path d="M8 18a5 5 0 015-5h15l6 7h17a5 5 0 015 5v23a5 5 0 01-5 5H13a5 5 0 01-5-5z"/>',
    "Favorites": '<path d="M32 10l7 14 16 3-12 11 3 16-14-7-14 7 3-16L9 27l16-3z"/>',
    "Workflows": '<rect x="8" y="11" width="15" height="15" rx="4"/><rect x="41" y="38" width="15" height="15" rx="4"/><rect x="8" y="38" width="15" height="15" rx="4"/><path d="M23 18h11v28h7M23 46h11" fill="none" stroke="white" stroke-width="4"/>',
    "Activity": '<path d="M9 33h11l7-18 11 34 7-16h10" fill="none" stroke="white" stroke-width="5" stroke-linecap="round"/>',
    "Settings": '<circle cx="32" cy="32" r="20"/><circle cx="32" cy="32" r="8" fill="none" stroke="#ada0df" stroke-width="5"/>',
    "Blender": '<path d="M8 15l18 6L15 8l22 14M8 34h17" fill="none" stroke="white" stroke-width="5" stroke-linecap="round"/><ellipse cx="37" cy="35" rx="18" ry="15"/><circle cx="37" cy="35" r="7" fill="#edb07b"/>',
    "Photoshop": '<text x="32" y="42" text-anchor="middle" font-size="29" font-family="Segoe UI" font-weight="600">Ps</text>',
    "Illustrator": '<text x="32" y="42" text-anchor="middle" font-size="29" font-family="Segoe UI" font-weight="600">Ai</text>',
    "After Effects": '<text x="32" y="42" text-anchor="middle" font-size="27" font-family="Segoe UI" font-weight="600">Ae</text>',
    "Fusion": '<circle cx="24" cy="25" r="12"/><circle cx="41" cy="25" r="9"/><circle cx="33" cy="44" r="11"/>',
}


def icon(name, size=48):
    color = COLORS.get(name, "#8875f0")
    drawing = PATHS.get(name, PATHS["Projects"])
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="' + color + '"/><stop offset="1" stop-color="' + color + '" stop-opacity=".76"/></linearGradient></defs><rect x="1" y="1" width="62" height="62" rx="18" fill="url(#g)"/><g fill="white">' + drawing + '</g></svg>'
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return QIcon(pixmap)


def stylesheet(dark=False):
    bg, card, text, muted, edge, selected = (
        ("#191c29", "#25293a", "#f2f1fa", "#b1b3cb", "#383d52", "#3c365a") if dark else
        ("#f5f4fb", "#ffffff", "#292a40", "#777b93", "#e7e6f2", "#eee9fc"))
    return """
    QWidget {color: TEXT; font-family: 'Segoe UI'; font-size: 13px;}
    QMainWindow, QDialog {background: BG;}
    QWidget#sidebar {background: CARD; border-right:1px solid EDGE;}
    QFrame#card {background:CARD; border:1px solid EDGE; border-radius:20px;}
    QFrame#hero {background: SELECTED; border:1px solid EDGE; border-radius:24px;}
    QLabel#title {font-size:32px; font-weight:650; letter-spacing:-1px;}
    QLabel#subtitle {color:MUTED; font-size:14px;}
    QLabel#section {font-size:18px; font-weight:600;}
    QLabel#eyebrow {color:#8875f0; font-size:11px; font-weight:700; letter-spacing:2px;}
    QPushButton {background:CARD; border:1px solid EDGE; border-radius:10px; padding:9px 15px; font-weight:550;}
    QPushButton:hover {background:SELECTED; border-color:#c2b6ec;}
    QPushButton:pressed {background:#ddd4f5; color:#37304d;}
    QPushButton:focus, QLineEdit:focus, QComboBox:focus {border:2px solid #8a75ea;}
    QPushButton#primary {background:#8875ed; color:white; border:none;}
    QPushButton#primary:hover {background:#7966de;}
    QPushButton#primary:disabled {background:#c5bce7; color:white;}
    QPushButton#nav {text-align:left; border:none; padding:12px; border-radius:12px; background:transparent;}
    QPushButton#nav:checked {background:SELECTED; color:#917dea;}
    QPushButton#nav:hover {background:SELECTED;}
    QPushButton#projectCard {text-align:left; padding:20px; background:CARD; border:1px solid EDGE; border-radius:20px; font-size:16px;}
    QPushButton:disabled {color:MUTED; background:BG;}
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {background:CARD; border:1px solid EDGE; border-radius:9px; padding:8px; selection-background-color:#8875ed;}
    QComboBox::drop-down {border:none; width:22px;}
    QComboBox QAbstractItemView {background:CARD; selection-background-color:SELECTED; color:TEXT;}
    QTableWidget, QListWidget, QTreeWidget {background:CARD; border:1px solid EDGE; border-radius:12px; gridline-color:EDGE; alternate-background-color:BG; selection-background-color:SELECTED; selection-color:TEXT;}
    QTableWidget::item {padding:8px; border-bottom:1px solid EDGE;}
    QHeaderView::section {background:BG; color:MUTED; border:none; padding:10px; font-weight:600;}
    QScrollArea, QStackedWidget {background:transparent; border:none;}
    QSplitter::handle {background:BG; width:9px;}
    QGraphicsView {border:1px solid EDGE; border-radius:12px;}
    QGroupBox {border:1px solid EDGE; border-radius:12px; margin-top:14px; padding:12px;}
    QGroupBox::title {subcontrol-origin:margin; left:12px; padding:0 6px;}
    QToolButton {background:CARD; border:1px solid EDGE; border-radius:8px; padding:5px;}
    QMenu {background:CARD; border:1px solid EDGE; padding:6px;}
    QMenu::item {padding:8px 20px; border-radius:6px;}
    QMenu::item:selected {background:SELECTED;}
    QScrollBar:vertical {background:transparent; width:8px; margin:0;}
    QScrollBar::handle:vertical {background:#c0bbd4; border-radius:4px; min-height:28px;}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height:0;}
    QProgressBar {background:EDGE; border:none; border-radius:4px; max-height:7px; text-align:center;}
    QProgressBar::chunk {background:#8875ed; border-radius:4px;}
    QToolTip {background:CARD; color:TEXT; border:1px solid EDGE; padding:8px;}
    QCheckBox {spacing:8px;}
    QStatusBar {background:BG; color:MUTED; border:none;}
    """.replace("SELECTED", selected).replace("MUTED", muted).replace("TEXT", text).replace("EDGE", edge).replace("CARD", card).replace("BG", bg)


def palette(dark=False):
    result = QPalette()
    for role, color in ((QPalette.Window, "#191c29" if dark else "#f5f4fb"),
                        (QPalette.Base, "#25293a" if dark else "#ffffff"),
                        (QPalette.WindowText, "#f2f1fa" if dark else "#292a40"),
                        (QPalette.Text, "#f2f1fa" if dark else "#292a40"),
                        (QPalette.Button, "#25293a" if dark else "#ffffff"),
                        (QPalette.ButtonText, "#f2f1fa" if dark else "#292a40"),
                        (QPalette.Highlight, "#8875ed"), (QPalette.HighlightedText, "#ffffff")):
        result.setColor(role, QColor(color))
    return result


def native_theme(widget, dark=False):
    """Clear upstream inline dark styles before applying shared light/dark tokens."""
    from PySide6.QtWidgets import QWidget
    foreground = "#f2f1fa" if dark else "#292a40"
    background = "#191c29" if dark else "#f5f4fb"
    surface = "#25293a" if dark else "#ffffff"
    for child in [widget] + widget.findChildren(QWidget):
        child.setStyleSheet("")
        child.setPalette(palette(dark))
    widget.setStyleSheet(stylesheet(dark) +
        " QWidget {background:" + background + ";color:" + foreground + ";}" +
        " QLabel {background:transparent;}" +
        " QTabBar::tab {background:" + surface + ";padding:9px 16px;border-radius:8px;margin:2px;}" +
        " QTabBar::tab:selected {background:#8875ed;color:white;}" +
        " QMenuBar {background:" + background + ";}" +
        " QMenuBar::item {padding:8px 12px;}" +
        " QGroupBox {background:" + surface + ";}" +
        " QTreeWidget, QListWidget, QTableView, QListView, QTreeView {background:" + surface + ";}")
    widget.setWindowIcon(icon("Workflows"))


def fade(widget, reduced=False):
    if reduced:
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(160)
    animation.setStartValue(0.55)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._fade = animation
    animation.start()
