"""Shared Neotrix design tokens, original SVG icons and lightweight animation."""
from functools import lru_cache
from pathlib import Path
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


@lru_cache(maxsize=128)
def icon(name, size=48):
    application_art = {'Blender':'blender','Photoshop':'photoshop','Illustrator':'illustrator',
                       'After Effects':'after-effects','Fusion':'fusion'}
    if name in application_art:
        asset=Path(__file__).resolve().parents[1]/'assets'/'app-icons'/(application_art[name]+'.png')
        if asset.is_file():
            return QIcon(str(asset))
    color = COLORS.get(name, "#8875f0")
    drawing = PATHS.get(name, PATHS["Projects"])
    light, deep = QColor(color).lighter(145).name(), QColor(color).darker(170).name()
    definitions = '<defs><linearGradient id="body" x1="0" y1="0" x2=".8" y2="1"><stop stop-color="' + light + '"/><stop offset=".42" stop-color="' + color + '"/><stop offset="1" stop-color="' + deep + '"/></linearGradient><linearGradient id="face" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#fff5d7"/><stop offset="1" stop-color="#f7b756"/></linearGradient><linearGradient id="shine" x1="0" y1="0" x2=".5" y2="1"><stop stop-color="white" stop-opacity=".7"/><stop offset="1" stop-color="white" stop-opacity="0"/></linearGradient></defs>'
    if name == "Brand":
        art = '<path d="M32 3L57 18V47L32 62 7 47V18Z" fill="url(#body)" stroke="#e5ccff" stroke-width=".7"/><path d="M32 3V32L7 18Z" fill="#e9c2ff"/><path d="M32 32L57 18V47L32 62Z" fill="#7029a2"/><path d="M32 32L7 18V47L32 62Z" fill="#bc6cde"/><path d="M32 6V31L10 18" fill="none" stroke="white" stroke-opacity=".6" stroke-width="1.3"/>'
    elif name == "Projects":
        art = '<path d="M6 17Q6 11 12 11H26L33 19H53Q59 19 59 25V51Q59 57 53 57H12Q6 57 6 51Z" fill="url(#body)"/><rect x="14" y="23" width="38" height="24" rx="3" fill="#fff3df" transform="rotate(-6 32 32)"/><path d="M8 31Q8 26 14 26H55Q61 26 60 32L56 52Q55 57 49 57H12Q7 57 7 52Z" fill="url(#face)" stroke="#fff0c1" stroke-width=".8"/><path d="M14 29H54" stroke="white" stroke-opacity=".75" stroke-linecap="round"/>'
    elif name == "Favorites":
        art = '<g fill="' + deep + '" transform="translate(0 3)">' + drawing + '</g><g fill="url(#body)" stroke="#ffc1df" stroke-width=".6">' + drawing + '</g><path d="M32 14L27 26 15 29" fill="none" stroke="white" stroke-opacity=".6" stroke-width="2" stroke-linecap="round"/>'
    else:
        art = '<rect x="5" y="7" width="54" height="54" rx="17" fill="' + deep + '"/><rect x="5" y="3" width="54" height="54" rx="17" fill="url(#body)"/><rect x="6" y="4" width="52" height="52" rx="16" fill="none" stroke="url(#shine)" stroke-width="1.5"/><g transform="translate(9 7) scale(.72)" fill="#1f1145" opacity=".24">' + drawing + '</g><g transform="translate(9 5) scale(.72)" fill="#fffaff">' + drawing + '</g>'
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="-8 -8 80 80">' + definitions + '<ellipse cx="33" cy="61" rx="24" ry="4" fill="#211040" opacity=".12"/>' + art + '</svg>'
    # Supersample original vectors so labels remain sharp on high-DPI Windows.
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def theme_tokens(dark=False):
    """Both appearances use colored surfaces; midnight reduces their luminance."""
    return (("#211447", "#342451", "#fff8ff", "#d3c4e3", "#5c437c", "#604080") if dark else
            ("#422273", "#573683", "#fffaff", "#e2cfee", "#8863a3", "#7951a5"))


def stylesheet(dark=False):
    from .typography import roles
    display_font, text_font = roles()
    bg, card, text, muted, edge, selected = theme_tokens(dark)
    return """
    QWidget {color: TEXT; font-family: 'FONT_TEXT'; font-size: 13px;}
    QMainWindow, QDialog {background: BG;}
    QMainWindow#workspaceWindow {background:transparent;}
    QWidget#caption {background:transparent;}
    QWidget#sidebar {background:rgba(27,10,58,45); border-right:1px solid rgba(255,255,255,24);}
    QFrame#card {background:qlineargradient(x1:0,y1:0,x2:.8,y2:1,stop:0 CARD,stop:1 BG); border:1px solid rgba(255,255,255,35); border-radius:20px;}
    QFrame#hero, QFrame#featureTile {background:transparent; border:none;}
    QFrame#hero QLabel, QFrame#featureTile QLabel {color:#ffffff; background:transparent;}
    QFrame#hero QLabel#subtitle, QFrame#featureTile QLabel#subtitle {color:#e7d5f5;}
    QFrame#hero QLabel#eyebrow, QFrame#featureTile QLabel#eyebrow {color:#e3c1f3; font-size:10px; letter-spacing:1px;}
    QFrame#hero QLabel#title {font-size:29px; font-weight:600;}
    QFrame#featureTile QLabel#section {font-size:21px; font-weight:600;}
    QFrame#hero QPushButton, QFrame#featureTile QPushButton {background:rgba(255,255,255,22); color:white; border:1px solid rgba(255,255,255,35);}
    QFrame#hero QPushButton:hover, QFrame#featureTile QPushButton:hover {background:rgba(255,255,255,42); border-color:rgba(255,255,255,75);}
    QFrame#hero QPushButton#primary {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #d25bdd,stop:1 #8c37bb);color:white;border:1px solid #df8fec;}
    QLabel#title {font-family:'FONT_DISPLAY';font-size:30px; font-weight:500; letter-spacing:-1px;}
    QLabel#subtitle {color:MUTED; font-size:14px;}
    QLabel#section {font-family:'FONT_DISPLAY';font-size:18px; font-weight:600;}
    QLabel#eyebrow {color:#e2b7f4; font-size:11px; font-weight:700; letter-spacing:2px;}
    QPushButton {background:CARD; border:1px solid EDGE; border-radius:10px; padding:9px 15px; font-weight:550;}
    QPushButton:hover {background:SELECTED; border-color:#c2b6ec;}
    QPushButton:pressed {background:#79489e; color:white;}
    QPushButton::menu-indicator {subcontrol-origin:padding; subcontrol-position:center right; right:5px; width:8px; height:8px;}
    QPushButton:focus, QLineEdit:focus, QComboBox:focus {border:2px solid #8a75ea;}
    QPushButton#primary {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ae57ce,stop:.48 #8651c2,stop:1 #6040a4); color:white; border:1px solid #b07ad4;}
    QPushButton#primary:hover {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #c16ade,stop:1 #7550ba);}
    QPushButton#primary:disabled {background:#624575; color:#d3c4e3;}
    QPushButton#nav {text-align:left; border:none; padding:12px; border-radius:12px; background:transparent;}
    QPushButton#nav:checked {background:transparent; color:white; border:none;}
    QPushButton#nav:hover {background:rgba(255,255,255,20);}
    QFrame#selectionRail {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ac61d0,stop:1 #7044ae);border:1px solid #bb87d8;border-radius:12px;}
    QPushButton#projectCard {text-align:left; padding:20px; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 CARD,stop:1 BG); border:1px solid EDGE; border-radius:20px; font-size:16px;}
    QPushButton#projectCard:hover {background:SELECTED;border-color:#b79bd8;}
    QPushButton:disabled {color:MUTED; background:BG;}
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {background:CARD; border:1px solid EDGE; border-radius:9px; padding:8px; selection-background-color:#8875ed;}
    QComboBox::drop-down {border:none; width:22px;}
    QComboBox QAbstractItemView {background:CARD; border:1px solid EDGE; border-radius:12px; selection-background-color:SELECTED; color:TEXT;}
    QTableWidget, QListWidget, QTreeWidget {background:CARD; border:1px solid EDGE; border-radius:12px; gridline-color:EDGE; alternate-background-color:BG; selection-background-color:SELECTED; selection-color:TEXT;}
    QTableWidget::item {padding:8px; border-bottom:1px solid EDGE;}
    QHeaderView::section {background:BG; color:MUTED; border:none; padding:10px; font-weight:600;}
    QHeaderView {background:BG;}
    QScrollArea, QStackedWidget {background:transparent; border:none;}
    QSplitter::handle {background:BG; width:9px;}
    QGraphicsView {border:1px solid EDGE; border-radius:12px;}
    QGroupBox {border:1px solid EDGE; border-radius:12px; margin-top:14px; padding:12px;}
    QGroupBox::title {subcontrol-origin:margin; left:12px; padding:0 6px;}
    QToolButton {background:CARD; border:1px solid EDGE; border-radius:8px; padding:5px;}
    QMenu {background:CARD; border:1px solid EDGE; border-radius:12px; padding:6px;}
    QMenu::item {padding:8px 20px; border-radius:6px;}
    QMenu::item:selected {background:SELECTED;}
    QScrollBar:vertical {background:transparent; width:0; margin:0;}
    QScrollBar::handle:vertical {background:#956dac; border-radius:4px; min-height:28px;}
    QScrollBar:horizontal {background:transparent; height:0;}
    QScrollBar::handle:horizontal {background:#956dac; border-radius:4px; min-width:28px;}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {width:0;}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height:0;}
    QProgressBar {background:EDGE; border:none; border-radius:4px; max-height:7px; text-align:center;}
    QProgressBar::chunk {background:#8875ed; border-radius:4px;}
    QToolTip {background:CARD; color:TEXT; border:1px solid EDGE; padding:8px;}
    QCheckBox {spacing:8px;}
    QStatusBar {background:BG; color:MUTED; border:none;}
    """.replace("FONT_DISPLAY", display_font).replace("FONT_TEXT", text_font).replace("SELECTED", selected).replace("MUTED", muted).replace("TEXT", text).replace("EDGE", edge).replace("CARD", card).replace("BG", bg)


def palette(dark=False):
    result = QPalette()
    bg, card, text, muted, edge, selected = theme_tokens(dark)
    for role, color in ((QPalette.Window, bg), (QPalette.Base, card),
                        (QPalette.AlternateBase, bg), (QPalette.WindowText, text),
                        (QPalette.Text, text), (QPalette.Button, card),
                        (QPalette.ButtonText, text), (QPalette.PlaceholderText, muted),
                        (QPalette.Highlight, selected), (QPalette.HighlightedText, text)):
        result.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        result.setColor(QPalette.Disabled, role, QColor(muted))
    return result


def native_theme(widget, dark=False):
    """Clear upstream inline dark styles before applying shared light/dark tokens."""
    from PySide6.QtWidgets import QWidget,QAbstractScrollArea,QMenu
    from .cards import round_surface
    background, surface, foreground, _, _, _ = theme_tokens(dark)
    for child in [widget] + widget.findChildren(QWidget):
        child.setStyleSheet("")
        child.setPalette(palette(dark))
        if isinstance(child,QAbstractScrollArea):
            child.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            child.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            round_surface(child)
            round_surface(child.viewport())
        elif isinstance(child,QMenu):
            round_surface(child)
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
