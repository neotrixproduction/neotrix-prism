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
    navigation = {'NavigationProjects':'projects', 'NavigationFavorites':'favorites',
                  'NavigationActivity':'activity', 'NavigationSettings':'settings'}
    if name in navigation:
        return QIcon(str(Path(__file__).resolve().parents[1]/'assets/nav-icons'/(navigation[name]+'.png')))
    generated = {'Projects':'projects', 'Files':'files', 'Versions':'versions',
                 'VERSION':'versions', 'Default':'default', 'Workspace':'files'}
    if name in generated:
        return QIcon(str(Path(__file__).resolve().parents[1]/'assets/ui-icons'/(generated[name]+'.png')))
    application_art = {'Blender':'blender','Photoshop':'photoshop','Illustrator':'illustrator',
                       'After Effects':'after-effects','Fusion':'fusion'}
    if name in application_art:
        asset=Path(__file__).resolve().parents[1]/'assets'/'app-icons'/(application_art[name]+'.png')
        if asset.is_file():
            return QIcon(str(asset))
    if name not in PATHS and name != 'Brand':
        return QIcon(str(Path(__file__).resolve().parents[1]/'assets/ui-icons/files.png'))
    color = COLORS.get(name, "#8875f0")
    drawing = PATHS.get(name, PATHS["Projects"])
    light, deep = QColor(color).lighter(145).name(), QColor(color).darker(170).name()
    definitions = '<defs><linearGradient id="body" x1="0" y1="0" x2=".8" y2="1"><stop stop-color="' + light + '"/><stop offset=".42" stop-color="' + color + '"/><stop offset="1" stop-color="' + deep + '"/></linearGradient><linearGradient id="face" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#fff5d7"/><stop offset="1" stop-color="#f7b756"/></linearGradient><linearGradient id="shine" x1="0" y1="0" x2=".5" y2="1"><stop stop-color="white" stop-opacity=".7"/><stop offset="1" stop-color="white" stop-opacity="0"/></linearGradient></defs>'
    if name == "Brand":
        art = '<path d="M32 3L57 18V47L32 62 7 47V18Z" fill="url(#body)" stroke="#e5ccff" stroke-width=".7"/><path d="M32 3V32L7 18Z" fill="#e9c2ff"/><path d="M32 32L57 18V47L32 62Z" fill="#7029a2"/><path d="M32 32L7 18V47L32 62Z" fill="#bc6cde"/><path d="M32 6V31L10 18" fill="none" stroke="white" stroke-opacity=".6" stroke-width="1.3"/>'
    elif name == "Projects":
        # Original project constellation: thick creative tiles orbit a prism.
        definitions += '<defs><linearGradient id="violet" x2=".8" y2="1"><stop stop-color="#efd4ff"/><stop offset=".42" stop-color="#aa77ff"/><stop offset="1" stop-color="#6239d0"/></linearGradient><linearGradient id="cyan" x2=".6" y2="1"><stop stop-color="#c6fbff"/><stop offset=".4" stop-color="#55d9f1"/><stop offset="1" stop-color="#2879ba"/></linearGradient><linearGradient id="coral" x2=".7" y2="1"><stop stop-color="#ffd0e7"/><stop offset=".45" stop-color="#fa7fae"/><stop offset="1" stop-color="#a93d83"/></linearGradient></defs>'
        art = '<path d="M14 20L46 16 51 46 19 51Z" fill="none" stroke="#bdd4ff" stroke-width="2" opacity=".55"/><g transform="rotate(-12 16 17)"><rect x="3" y="6" width="24" height="24" rx="7" fill="#375397"/><rect x="3" y="2" width="24" height="24" rx="7" fill="url(#cyan)" stroke="#d9fbff"/><path d="M8 7H21" stroke="white" stroke-width="1.3" stroke-linecap="round" opacity=".75"/></g><g transform="rotate(12 48 19)"><rect x="38" y="10" width="23" height="24" rx="7" fill="#72316c"/><rect x="38" y="6" width="23" height="24" rx="7" fill="url(#coral)" stroke="#ffdeef"/><path d="M43 11H55" stroke="white" stroke-width="1.3" stroke-linecap="round" opacity=".75"/></g><g transform="rotate(-6 35 47)"><rect x="21" y="35" width="29" height="27" rx="8" fill="#382875"/><rect x="21" y="30" width="29" height="27" rx="8" fill="url(#violet)" stroke="#e6d4ff"/><path d="M26 35H44" stroke="white" stroke-width="1.5" stroke-linecap="round" opacity=".8"/></g><path d="M31 17L45 26V39L31 48 17 39V26Z" fill="#413583" stroke="#d4d2ff"/><path d="M31 17L45 26 31 35 17 26Z" fill="#eee1ff"/><path d="M17 26L31 35V48L17 39Z" fill="#b68bff"/><path d="M31 35L45 26V39L31 48Z" fill="#6946cd"/><path d="M31 21L40 26" stroke="white" stroke-width="1.5" stroke-linecap="round"/><circle cx="9" cy="47" r="3" fill="#86f4e2"/><circle cx="57" cy="45" r="2" fill="#ffc6ed"/>'
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


@lru_cache(maxsize=1)
def check_icon():
    """Dark check mark for the white checked box, written once to the user dir."""
    from .storage import user_dir
    path = user_dir()/'ui-check.svg'
    if not path.exists():
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">'
                        '<path d="M4.5 9.4l3 3 6-6.6" fill="none" stroke="#1a1430" stroke-width="2.2" '
                        'stroke-linecap="round" stroke-linejoin="round"/></svg>', encoding='utf-8')
    return path.as_posix()


def search_icon(size=18):
    """A soft magnifier glyph for search fields."""
    from PySide6.QtGui import QPen
    from PySide6.QtCore import QRectF
    pixmap = QPixmap(size*2, size*2)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(255, 255, 255, 190), 3.4, Qt.SolidLine, Qt.RoundCap))
    p.drawEllipse(QRectF(size*.42, size*.42, size*.92, size*.92))
    p.drawLine(int(size*1.22), int(size*1.22), int(size*1.6), int(size*1.6))
    p.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def theme_tokens(dark=True):
    """One midnight palette; retain the argument for existing host callers."""
    return ("#211447", "#342451", "#fff8ff", "#d3c4e3", "#5c437c", "#604080")


def stylesheet(dark=True):
    from .typography import roles
    display_font, text_font = roles()
    bg, card, text, muted, edge, selected = theme_tokens(dark)
    return """
    QWidget {color: TEXT; font-family: 'FONT_TEXT'; font-size: 14px;}
    QMainWindow, QDialog {background: BG;}
    QMainWindow#workspaceWindow {background:transparent;}
    QWidget#caption {background:transparent;}
    QWidget#sidebar {background:rgba(8,8,30,24); border:none;}
    QFrame#card {background:qlineargradient(x1:0,y1:0,x2:.8,y2:1,stop:0 rgba(255,255,255,38),stop:1 rgba(255,255,255,16)); border:1px solid rgba(255,255,255,46); border-radius:20px;}
    QFrame#hero, QFrame#featureTile {background:transparent; border:none;}
    QFrame#hero QLabel, QFrame#featureTile QLabel {color:#ffffff; background:transparent;}
    QFrame#hero QLabel#subtitle, QFrame#featureTile QLabel#subtitle {color:#e7d5f5;}
    QFrame#hero QLabel#eyebrow, QFrame#featureTile QLabel#eyebrow {color:#e3c1f3; font-size:10px; letter-spacing:1px;}
    QFrame#hero QLabel#title {font-size:29px; font-weight:600;}
    QFrame#featureTile QLabel#section {font-size:21px; font-weight:600;}
    QFrame#hero QPushButton, QFrame#featureTile QPushButton {background:rgba(255,255,255,22); color:white; border:1px solid rgba(255,255,255,35);}
    QFrame#hero QPushButton:hover, QFrame#featureTile QPushButton:hover {background:rgba(255,255,255,42); border-color:rgba(255,255,255,75);}
    QFrame#hero QPushButton#primary {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #d25bdd,stop:1 #8c37bb);color:white;border:1px solid #df8fec;}
    QLabel#title {font-family:'FONT_DISPLAY';font-size:27px; font-weight:500;}
    QLabel#subtitle {color:MUTED; font-size:14px;}
    QLabel#section {font-family:'FONT_DISPLAY';font-size:18px; font-weight:600;}
    QLabel#sidebarBrand {font-size:11px; font-weight:600; color:#e6deef; background:transparent;}
    QLabel#eyebrow {color:#e2b7f4; font-size:11px; font-weight:700; letter-spacing:2px;}
    QPushButton {background:rgba(255,255,255,22); border:1px solid rgba(255,255,255,40); border-radius:10px; padding:9px 15px; font-weight:550;}
    QPushButton:hover {background:rgba(255,255,255,34); border-color:rgba(255,255,255,70);}
    QPushButton:pressed {background:rgba(255,255,255,48); color:white;}
    QPushButton::menu-indicator {subcontrol-origin:padding; subcontrol-position:center right; right:5px; width:8px; height:8px;}
    QPushButton:focus, QLineEdit:focus, QComboBox:focus {border:2px solid rgba(255,255,255,150);}
    QPushButton#primary {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:1 #e9e4f4); color:#1a1430; border:1px solid rgba(255,255,255,230); font-weight:650;}
    QPushButton#primary:hover {background:#ffffff; color:#120d26;}
    QPushButton#primary:pressed {background:#dcd6ea; color:#120d26;}
    QPushButton#primary:disabled {background:rgba(255,255,255,40); color:rgba(255,255,255,120); border-color:rgba(255,255,255,40);}
    QPushButton#nav {border:none; padding:8px 8px 8px 16px; text-align:left; border-radius:16px; background:transparent; font-size:13px; font-weight:500; color:#e8e3ef;}
    QPushButton#nav:checked {background:transparent; color:white; border:none;}
    QPushButton#nav:hover {background:rgba(255,255,255,20);}
    QFrame#selectionRail {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(237,177,255,44),stop:1 rgba(158,153,255,18));border:1px solid rgba(229,196,255,55);border-radius:16px;}
    QPushButton#projectCard {text-align:left; padding:20px; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 CARD,stop:1 BG); border:1px solid EDGE; border-radius:20px; font-size:16px;}
    QPushButton#projectCard:hover {background:SELECTED;border-color:#b79bd8;}
    QPushButton#recentProject {text-align:left; padding:8px 12px; background:rgba(255,255,255,18); border:1px solid rgba(255,255,255,24); border-radius:12px;}
    QPushButton:disabled {color:rgba(255,255,255,105); background:rgba(255,255,255,10); border-color:rgba(255,255,255,22);}
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {background:rgba(6,4,22,70); border:1px solid rgba(255,255,255,40); border-radius:12px; padding:8px; color:#fbf8ff; selection-background-color:rgba(255,255,255,70);}
    QLineEdit, QComboBox, QSpinBox {font-weight:500;}
    QLineEdit, QTextEdit, QPlainTextEdit {placeholder-text-color:#bfc2d8;}
    QLineEdit:hover, QComboBox:hover {border-color:rgba(255,255,255,80);}
    QComboBox::drop-down {border:none; width:22px;}
    QComboBox QAbstractItemView {background:#1d1636; border:1px solid rgba(255,255,255,40); border-radius:12px; selection-background-color:rgba(255,255,255,40); color:TEXT;}
    QTableWidget, QListWidget, QTreeWidget {background:CARD; border:1px solid EDGE; border-radius:12px; gridline-color:EDGE; alternate-background-color:BG; selection-background-color:SELECTED; selection-color:TEXT;}
    QTableWidget::item {padding:8px; border-bottom:1px solid EDGE;}
    QHeaderView::section {background:BG; color:MUTED; border:none; padding:10px; font-weight:600;}
    QHeaderView {background:BG;}
    QTableWidget#collectionTable {background:transparent; border:none; gridline-color:transparent; alternate-background-color:transparent; selection-background-color:rgba(255,255,255,42); selection-color:#ffffff;}
    QTableWidget#collectionTable::item {background:transparent; padding:10px; border:none; border-bottom:1px solid rgba(255,255,255,14); color:#fffaff;}
    QTableWidget#collectionTable::item:hover {background:rgba(255,255,255,17);}
    QTableWidget#collectionTable::item:selected {background:rgba(255,255,255,42); color:#ffffff;}
    QTableWidget#collectionTable QHeaderView {background:transparent; border:none;}
    QTableWidget#collectionTable QHeaderView::section {background:rgba(255,255,255,16); color:#fff1f9; border:none; border-bottom:1px solid rgba(255,255,255,24); padding:12px 10px; font-weight:600;}
    QTableWidget#collectionTable QTableCornerButton::section {background:transparent; border:none;}
    QPlainTextEdit#activityDetail {background:rgba(176,235,226,20); border:1px solid rgba(201,249,241,35); selection-background-color:rgba(167,229,215,70); color:#eefdf9;}
    QScrollArea, QStackedWidget {background:transparent; border:none;}
    QSplitter::handle {background:BG; width:9px;}
    QGraphicsView {border:1px solid EDGE; border-radius:12px;}
    QGroupBox {border:1px solid EDGE; border-radius:12px; margin-top:14px; padding:12px;}
    QGroupBox::title {subcontrol-origin:margin; left:12px; padding:0 6px;}
    QToolButton {background:CARD; border:1px solid EDGE; border-radius:8px; padding:5px;}
    QMenu {background:#1d1636; border:1px solid rgba(255,255,255,40); border-radius:12px; padding:6px;}
    QMenu::item {padding:8px 20px; border-radius:6px;}
    QMenu::item:selected {background:rgba(255,255,255,36);}
    QScrollBar:vertical {background:transparent; width:0; margin:0;}
    QScrollBar::handle:vertical {background:#956dac; border-radius:4px; min-height:28px;}
    QScrollBar:horizontal {background:transparent; height:0;}
    QScrollBar::handle:horizontal {background:#956dac; border-radius:4px; min-width:28px;}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {width:0;}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height:0;}
    QProgressBar {background:rgba(255,255,255,30); border:none; border-radius:4px; max-height:7px; text-align:center;}
    QProgressBar::chunk {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba(255,255,255,120),stop:1 #ffffff); border-radius:4px;}
    QLabel#statusLine {color:rgba(236,230,246,150); font-size:12px; background:transparent;}
    QPushButton#quietAction {background:transparent; border:none; color:rgba(236,230,246,150); font-size:12px; font-weight:500; padding:4px 10px; border-radius:8px;}
    QPushButton#quietAction:hover {color:#ffffff; background:rgba(255,255,255,14);}
    QPushButton#quietAction:pressed {background:rgba(255,255,255,24);}
    QSlider {background:transparent; min-height:22px;}
    QSlider::groove:horizontal {height:6px; border-radius:3px; background:rgba(255,255,255,30);}
    QSlider::sub-page:horizontal {height:6px; border-radius:3px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba(255,255,255,120),stop:1 #ffffff);}
    QSlider::handle:horizontal {width:16px; height:16px; margin:-5px 0; border-radius:8px; background:#ffffff; border:1px solid rgba(255,255,255,230);}
    QSlider::handle:horizontal:hover {background:#f4efff;}
    QSlider::sub-page:horizontal:disabled {background:rgba(255,255,255,40);}
    QSlider::handle:horizontal:disabled {background:rgba(255,255,255,90); border-color:rgba(255,255,255,40);}
    QToolTip {background:#1d1636; color:TEXT; border:1px solid rgba(255,255,255,50); padding:8px;}
    QCheckBox {spacing:10px;}
    QCheckBox::indicator {width:18px; height:18px; border-radius:6px; border:1px solid rgba(255,255,255,90); background:rgba(255,255,255,22);}
    QCheckBox::indicator:hover {border-color:rgba(255,255,255,170); background:rgba(255,255,255,38);}
    QCheckBox::indicator:checked {background:#ffffff; border-color:#ffffff; image:url(CHECK_ICON);}
    QStatusBar {background:BG; color:MUTED; border:none;}
    """.replace("CHECK_ICON", check_icon()).replace("FONT_DISPLAY", display_font).replace("FONT_TEXT", text_font).replace("SELECTED", selected).replace("MUTED", muted).replace("TEXT", text).replace("EDGE", edge).replace("CARD", card).replace("BG", bg)


def palette(dark=True):
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


def native_theme(widget, dark=True):
    """Clear upstream inline styles before applying the shared midnight theme."""
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
