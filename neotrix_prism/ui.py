"""Neotrix's Windows workspace, sharing the same Qt shell with creative integrations."""
import json
import os
import threading
import time
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PySide6.QtGui import QPixmap, QIcon, QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QStackedWidget, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSplitter, QScrollArea, QProgressBar, QMessageBox, QFileDialog,
    QPlainTextEdit, QCheckBox, QFormLayout, QDialog, QDialogButtonBox, QMenu, QLayout, QSizePolicy, QAbstractScrollArea)
from . import __version__, apps, indexer
from .storage import Settings, user_dir, atomic_json, read_json, history, activity
from .design import icon, stylesheet, fade, palette, native_theme
from .surfaces import Atmosphere, GradientTile, WorkspaceArt
from .motion import MotionButton, MotionIcon, OrbButton, SceneTransition, reveal_page, tween, enabled
from .window_chrome import RoundedShell, Caption, ResizeFrame
from .project_browser import GridCards, FileList, ProjectArtwork
from .project_metadata import StageStore, STAGES
from .cards import CardSurface, round_surface


class Worker(QThread):
    result = Signal(object)
    failure = Signal(str)
    progress = Signal(int, str)
    node = Signal(str, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.cancel = threading.Event()

    def run(self):
        try:
            self.result.emit(self.fn(self))
        except Exception as exc:
            self.failure.emit(str(exc))


def label(text, name=None, wrap=False):
    item = QLabel(text)
    if name:
        item.setObjectName(name)
    item.setWordWrap(wrap)
    return item


def button(text, callback, primary=False):
    item = MotionButton(text)
    item.setCursor(Qt.PointingHandCursor)
    if primary:
        item.setObjectName("primary")
    item.clicked.connect(callback)
    return item


def card():
    item = QFrame()
    item.setObjectName("card")
    layout = QVBoxLayout(item)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    return item, layout


def table(columns):
    item = QTableWidget(0, len(columns))
    item.setHorizontalHeaderLabels(columns)
    item.setSelectionBehavior(QAbstractItemView.SelectRows)
    item.setSelectionMode(QAbstractItemView.SingleSelection)
    item.setEditTriggers(QAbstractItemView.NoEditTriggers)
    item.setAlternatingRowColors(True)
    item.verticalHeader().hide()
    item.verticalHeader().setDefaultSectionSize(49)
    item.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    item.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    return item


class MainWindow(QMainWindow):
    def __init__(self, settings=None, core=None):
        super().__init__()
        from .typography import initialize
        initialize()
        self.settings = settings or Settings()
        self.core = core
        self.projects, self.files, self.display_files, self.jobs = [], [], [], []
        self.project, self.preview = None, None
        self.setWindowTitle("Neotrix Prism")
        self.setObjectName("workspaceWindow")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowIcon(icon("Brand"))
        self.resize(1360, 900)
        self.setMinimumSize(1024, 720)
        shell = RoundedShell()
        self.setCentralWidget(shell)
        self.shell_layout = QVBoxLayout(shell)
        self.shell_layout.setContentsMargins(8, 8, 8, 8)
        self.shell_layout.setSpacing(0)
        self.surface = Atmosphere()
        self.shell_layout.addWidget(self.surface)
        surface_layout = QVBoxLayout(self.surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)
        self.caption = Caption(self)
        surface_layout.addWidget(self.caption)
        central = QWidget()
        surface_layout.addWidget(central, 1)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QWidget()
        self.sidebar = sidebar
        self.compact_sidebar = False
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(202)
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(18, 26, 18, 20)
        nav_layout.setSpacing(8)
        brand = QHBoxLayout()
        mark = QLabel()
        mark.setFixedSize(37, 37)
        mark.setPixmap(icon("Brand", 37).pixmap(37, 37))
        brand.addWidget(mark)
        self.brand_label = label("NEOTRIX\nPrism", "section")
        brand.addWidget(self.brand_label)
        nav_layout.addLayout(brand)
        nav_layout.addSpacing(35)
        self.nav = {}
        for name in ("Home", "Projects", "Favorites", "Activity", "Settings"):
            item = button(name, lambda checked=False, n=name: self.navigate(n))
            item.setObjectName("nav")
            item.setCheckable(True)
            item.setToolTip(name)
            item.setIcon(icon(name, 28))
            item.setIconSize(QSize(26, 26))
            nav_layout.addWidget(item)
            self.nav[name] = item
        nav_layout.addStretch()
        self.storage_label = label("Relay\nConnecting…", "subtitle", True)
        nav_layout.addWidget(self.storage_label)
        self.version_label = label("Neotrix Prism " + __version__, "subtitle")
        nav_layout.addWidget(self.version_label)
        self.selection_rail = QFrame(sidebar)
        self.selection_rail.setObjectName("selectionRail")
        self.selection_rail.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.selection_rail.lower()
        layout.addWidget(sidebar)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(30, 26, 30, 8)
        body.setSpacing(18)
        header = QHBoxLayout()
        left = QVBoxLayout()
        self.page_title = label("Your creative workspace", "title")
        self.page_subtitle = label("Everything you need to pick up where you left off.", "subtitle")
        left.addWidget(self.page_title)
        left.addWidget(self.page_subtitle)
        header.addLayout(left, 1)
        pipeline = MotionButton("Pipeline tools")
        pipeline.setIcon(icon("Settings", 22))
        menu = QMenu(pipeline)
        for title, action in (("Save New Version", self.save_current_version), ("Prism managed-project browser", self.native_browser),
                              ("State Manager", self.state_manager), ("Prism project settings", self.native_settings)):
            entry = menu.addAction(title)
            entry.triggered.connect(action)
        pipeline.setMenu(menu)
        header.addWidget(pipeline)
        body.addLayout(header)
        self.stack = QStackedWidget()
        self.pages = {}
        body.addWidget(self.stack, 1)
        footer_host = QWidget()
        footer_host.setFixedHeight(84)
        footer = QGridLayout(footer_host)
        footer.setContentsMargins(0,0,0,0)
        footer.setColumnStretch(0,1)
        footer.setColumnStretch(2,1)
        self.status = label("Ready", "subtitle")
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        footer.addWidget(self.status,0,0)
        self.orb = OrbButton()
        self.orb.clicked.connect(lambda: self.cancel_jobs() if self.jobs else self.navigate("Projects"))
        orb_policy = self.orb.sizePolicy()
        orb_policy.setRetainSizeWhenHidden(True)
        self.orb.setSizePolicy(orb_policy)
        footer.addWidget(self.orb,0,1,Qt.AlignCenter)
        task_controls = QWidget()
        task_controls.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        task_layout = QHBoxLayout(task_controls)
        task_layout.setContentsMargins(0,0,0,0)
        task_layout.addStretch()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.hide()
        task_layout.addWidget(self.progress_bar)
        self.cancel_button = button("Cancel", self.cancel_jobs)
        self.cancel_button.hide()
        task_layout.addWidget(self.cancel_button)
        footer.addWidget(task_controls,0,2)
        body.addWidget(footer_host)
        layout.addWidget(content, 1)
        self.build_home()
        self.build_projects()
        self.build_favorites()
        self.build_activity()
        self.build_settings()
        self.apply_theme()
        self.resize_frame = ResizeFrame(self)
        refresh = QAction(self)
        refresh.setShortcut(QKeySequence.Refresh)
        refresh.triggered.connect(self.refresh)
        self.addAction(refresh)
        back = QAction(self)
        back.setShortcut(QKeySequence('Alt+Left'))
        back.triggered.connect(self.browse_back)
        self.addAction(back)
        self.navigate("Home")
        self.load_projects()

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        self.pages[name] = widget
        self.stack.addWidget(widget)
        return layout

    def apply_theme(self):
        if self.settings.data["reduced_motion"]:
            transition = getattr(self, '_scene_transition', None)
            if transition:
                transition.finish()
                self._scene_transition = None
            from PySide6.QtCore import QVariantAnimation
            for animation in self.findChildren(QVariantAnimation):
                animation.stop()
            for widget in self.findChildren(QWidget):
                if widget.graphicsEffect():
                    widget.setGraphicsEffect(None)
            self.sidebar.setFixedWidth(78 if self.compact_sidebar else 202)
        dark = self.settings.data["theme"] == "dark"
        self.surface.dark = dark
        self.surface.update()
        QApplication.instance().setPalette(palette(dark))
        self.setStyleSheet(stylesheet(dark))
        for scroll in self.findChildren(QScrollArea):
            scroll.viewport().setAutoFillBackground(False)
            if scroll.widget():
                scroll.widget().setAutoFillBackground(False)
        for scroll in self.findChildren(QAbstractScrollArea):
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            round_surface(scroll)
            round_surface(scroll.viewport())
        for menu in self.findChildren(QMenu):
            round_surface(menu)
        for surface in self.findChildren(CardSurface):
            if self.settings.data['reduced_motion']:
                surface.hover=0
                surface.advance(surface.target)
            surface.update()
        for widget in self.findChildren(MotionIcon):
            if not enabled(widget):
                for key in ("_hover", "_reveal"):
                    animation = getattr(widget, key, None)
                    if animation:
                        animation.stop()
                widget.set_hover(0)
                widget.set_reveal(1)
        self.orb.set_busy(bool(self.jobs))
        self.progress_bar.setVisible(bool(self.jobs) and not self.settings.data["reduced_motion"])

    def move_selection(self, name):
        target = self.nav[name].geometry()
        if not enabled(self) or not self.selection_rail.isVisible():
            self.selection_rail.setGeometry(target)
            self.selection_rail.show()
            return
        old = getattr(self, "_selection_motion", None)
        if old:
            old.stop()
            old.deleteLater()
        animation = QPropertyAnimation(self.selection_rail, b"geometry", self)
        animation.setStartValue(self.selection_rail.geometry())
        animation.setEndValue(target)
        animation.setDuration(320)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        self._selection_motion = animation
        animation.start()

    def toggle_sidebar(self):
        self.compact_sidebar = not self.compact_sidebar
        for name, item in self.nav.items():
            item.setText("" if self.compact_sidebar else name)
        self.brand_label.setVisible(not self.compact_sidebar)
        self.storage_label.setVisible(not self.compact_sidebar)
        self.version_label.setVisible(not self.compact_sidebar)
        self.caption.collapse.setText("›" if self.compact_sidebar else "‹")
        def step(value):
            self.sidebar.setFixedWidth(int(value))
            current = next((name for name, item in self.nav.items() if item.isChecked()), "Home")
            self.selection_rail.setGeometry(self.nav[current].geometry())
        tween(self, "_sidebar_motion", self.sidebar.width(), 78 if self.compact_sidebar else 202, step, 380)

    def navigate(self, name, origin=None):
        previous = self.stack.currentWidget()
        old_transition = getattr(self, '_scene_transition', None)
        if old_transition:
            old_transition.finish()
            self._scene_transition = None
        outgoing = previous.grab() if previous and previous is not self.pages[name] and enabled(self) and self.isVisible() else None
        direction = 1 if previous is None or self.stack.indexOf(previous) <= self.stack.indexOf(self.pages[name]) else -1
        titles = {"Home": ("Your creative workspace", "Everything you need to pick up where you left off."),
                  "Projects": ("Projects", "Find the right project. Open the right version."),
                  "Favorites": ("Your favorites", "The projects and files you keep close."),
                  "Activity": ("Your activity", "A clear record of files opened and versions saved."),
                  "Settings": ("Make it yours", "Storage, applications and the way your workspace feels.")}
        self.page_title.setText(titles[name][0])
        self.page_subtitle.setText(titles[name][1])
        self.page_title.setAlignment(Qt.AlignCenter if name == "Home" else Qt.AlignLeft)
        self.page_subtitle.setAlignment(Qt.AlignCenter if name == "Home" else Qt.AlignLeft)
        for key, nav in self.nav.items():
            nav.setChecked(key == name)
        self.stack.setCurrentWidget(self.pages[name])
        self.surface.focus_scene(self.stack.currentIndex())
        self.orb.setVisible(name == "Home" or bool(self.jobs))
        QTimer.singleShot(0, self, lambda: self.move_selection(name))
        if name == "Activity":
            self.refresh_history()
        elif name == "Favorites":
            self.refresh_favorites()
        self.pages[name].setGraphicsEffect(None)
        if outgoing is not None:
            self._scene_transition = SceneTransition(self.stack, outgoing, origin, direction)
            transition = self._scene_transition
            transition.destroyed.connect(lambda: setattr(self, '_scene_transition', None) if getattr(self, '_scene_transition', None) is transition else None)
        elif name != 'Home':
            reveal_page(self.pages[name])
        if name == "Home":
            def introduce():
                if self.stack.currentWidget() is not self.pages['Home']:
                    return
                for i, tile in enumerate(self.pages['Home'].findChildren(GradientTile)):
                    QTimer.singleShot(i*65, tile, lambda t=tile: reveal_page(t) if t.isVisible() else None)
                for i, artwork in enumerate(self.pages[name].findChildren(MotionIcon)):
                    artwork.appear(i * 90)
            QTimer.singleShot(430 if outgoing is not None else 0, self, introduce)

    def build_home(self):
        outer = self.page("Home")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumHeight(510)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        overview = QHBoxLayout()
        for tile_index, (name, title, description) in enumerate((
            ("Projects", "All your projects", "Browse working files across every creative application."),
            ("Favorites", "Your best, on hand", "Keep favorite projects and files one click away."))):
            frame = GradientTile(name)
            inner = QVBoxLayout(frame)
            inner.setContentsMargins(22, 18, 22, 20)
            inner.setSpacing(10)
            top = QHBoxLayout()
            top.addWidget(label({"Projects": "PROJECT LIBRARY", "Favorites": "FAVORITES"}[name], "eyebrow", True), 1)
            item = MotionIcon(name, 112)
            top.addWidget(item)
            inner.addLayout(top)
            inner.addWidget(label(title, "section", True))
            inner.addWidget(label(description, "subtitle", True))
            inner.addStretch()
            inner.addWidget(button("Open " + name.lower(), lambda checked=False, n=name, f=frame: self.navigate(n, QRect(f.mapTo(self.stack, QPoint(0,0)), f.size()))))
            overview.addWidget(frame, 100)
            frame.hover_changed.connect(lambda value, i=tile_index: overview.setStretch(i, int(100 + (65 if self.width()>1150 else 18) * max(0,value))))
        layout.addLayout(overview, 3)
        row = QHBoxLayout()
        recent_tile = GradientTile("Recent")
        recent_layout = QVBoxLayout(recent_tile)
        recent_layout.setContentsMargins(22, 18, 22, 20)
        recent_header = QHBoxLayout()
        recent_header.addWidget(label("Pick up where you left off", "section", True), 1)
        recent_header.addWidget(MotionIcon("Projects", 65))
        recent_layout.addLayout(recent_header)
        self.recent_container = QWidget()
        self.recent_grid = QGridLayout(self.recent_container)
        self.recent_grid.setContentsMargins(0, 0, 0, 0)
        recent_layout.addWidget(self.recent_container)
        recent_layout.addStretch()
        row.addWidget(recent_tile, 3)
        storage_tile = GradientTile("Storage")
        storage_layout = QVBoxLayout(storage_tile)
        storage_layout.setContentsMargins(22, 18, 22, 20)
        storage_header = QHBoxLayout()
        storage_header.addWidget(label("Your creative library", "section", True), 1)
        storage_header.addWidget(MotionIcon("Activity", 85))
        storage_layout.addLayout(storage_header)
        self.home_storage = label("Relay · Connecting…", "subtitle", True)
        storage_layout.addWidget(self.home_storage)
        storage_layout.addStretch()
        storage_layout.addWidget(button("Manage storage", lambda: self.navigate("Settings")))
        row.addWidget(storage_tile, 2)
        layout.addLayout(row, 2)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def update_recent(self):
        self.clear_layout(self.recent_grid)
        for i, path in enumerate(self.settings.data["recent"][:4]):
            item = button(Path(path).name + "\nContinue project  →", lambda checked=False, p=path: self.open_project(p))
            item.setObjectName("projectCard")
            item.setMinimumHeight(68)
            item.setIcon(QIcon(self.artwork.request(path)) if hasattr(self,'artwork') else icon("Projects",38))
            item.setIconSize(QSize(38, 38))
            self.recent_grid.addWidget(item, i // 2, i % 2)
        if not self.settings.data["recent"]:
            self.recent_grid.addWidget(label("Open a project to see it here.", "subtitle"), 0, 0)

    def build_projects(self):
        layout = self.page("Projects")
        project_controls = QHBoxLayout()
        self.project_search = QLineEdit()
        self.project_search.setPlaceholderText("Search projects")
        self.project_search.textChanged.connect(self.search_projects)
        project_controls.addWidget(self.project_search, 1)
        self.project_picker = QComboBox()
        self.project_picker.setMinimumWidth(160)
        self.project_picker.activated.connect(lambda i: self.open_project(self.project_picker.itemData(i)))
        project_controls.addWidget(self.project_picker)
        project_controls.addWidget(button("Browse projects", self.browse_projects))
        project_controls.addWidget(button("‹ Back", self.browse_back))
        project_controls.addWidget(button("Refresh", self.refresh))
        layout.addLayout(project_controls)
        self.project_views = QWidget()
        shelf_layout = QVBoxLayout(self.project_views)
        shelf_layout.setContentsMargins(0,0,0,0)
        self.artwork = ProjectArtwork(self)
        self.artwork.changed.connect(self.project_artwork_loaded)
        self.project_cards = GridCards()
        self.project_cards.activated.connect(lambda index: self.open_project(self.filtered_projects[index]))
        shelf_layout.addWidget(self.project_cards,1)
        self.project_views.setMinimumHeight(245)
        layout.addWidget(self.project_views,1)
        self.work_panel = QWidget()
        layout.addWidget(self.work_panel,1)
        layout = QVBoxLayout(self.work_panel)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(16)
        self.work_panel.hide()
        self.breadcrumb = label("Select a project to explore its working files.", "subtitle")
        self.breadcrumb.setTextFormat(Qt.RichText)
        self.breadcrumb.linkActivated.connect(self.breadcrumb_clicked)
        self.breadcrumb.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.breadcrumb.setFocusPolicy(Qt.StrongFocus)
        layout.addWidget(self.breadcrumb)
        self.choice_cards = GridCards()
        self.choice_cards.card_height = 216
        self.choice_cards.activated.connect(self.choice_selected)
        layout.addWidget(self.choice_cards,1)
        self.file_controls = QWidget()
        controls_layout = QVBoxLayout(self.file_controls)
        controls_layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.file_controls)
        row = QHBoxLayout()
        self.file_search = QLineEdit()
        self.file_search.setPlaceholderText("Search filenames, shots or paths")
        self.file_search.textChanged.connect(self.filter_files)
        row.addWidget(self.file_search, 1)
        self.file_kind = QComboBox()
        self.file_kind.addItem("Working files", "working")
        self.file_kind.addItem("Outputs & previews", "output")
        self.file_kind.currentIndexChanged.connect(self.filter_files)
        row.addWidget(self.file_kind)
        self.filters = {}
        for key, title in (("application", "All applications"), ("department", "All departments")):
            combo = QComboBox()
            combo.addItem(title, "")
            combo.currentIndexChanged.connect(self.filter_files)
            row.addWidget(combo)
            self.filters[key] = combo
        controls_layout.addLayout(row)
        row = QHBoxLayout()
        for key, title in (("shot", "All shots"), ("version", "All save revisions")):
            combo = QComboBox()
            combo.addItem(title, "")
            combo.currentIndexChanged.connect(self.filter_files)
            row.addWidget(combo, 1)
            self.filters[key] = combo
        controls_layout.addLayout(row)
        split = QSplitter()
        self.file_split = split
        self.file_cards = FileList()
        self.file_cards.selection_changed.connect(self.update_details)
        self.file_cards.activated.connect(lambda index: self.open_selected())
        split.addWidget(self.file_cards)
        detail, inner = card()
        inner.setContentsMargins(12,12,12,12)
        inner.setSpacing(6)
        self.details_panel = detail
        detail.setMinimumWidth(220)
        detail.setMaximumWidth(280)
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setFixedHeight(78)
        inner.addWidget(self.preview_image)
        self.detail_name = label("Select a working file", "section", True)
        inner.addWidget(self.detail_name)
        from PySide6.QtGui import QTextOption
        self.detail_info = QPlainTextEdit('Its details and actions will appear here.')
        self.detail_info.setReadOnly(True)
        self.detail_info.setWordWrapMode(QTextOption.WrapAnywhere)
        self.detail_info.setMinimumHeight(40)
        self.detail_info.setStyleSheet('background: transparent; color: #e2cfee; border: none; padding: 6px;')
        inner.addWidget(self.detail_info,1)
        self.file_actions = []
        action_row=QHBoxLayout()
        action_row.setSpacing(6)
        inner.addLayout(action_row)
        more_menu = QMenu(detail)
        round_surface(more_menu)
        for index,(text, callback, primary) in enumerate((("Open file", self.open_selected, True), ("Open with…", self.open_with, False),
                                         ("Save new version", self.save_selected_version, False),
                                         ("Reveal in Explorer", self.reveal_selected, False), ("Copy path", self.copy_selected, False),
                                         ("Favorite file", self.favorite_selected, False))):
            if index in (0,2):
                item = button('Open file' if index==0 else 'Save version',callback,primary)
                item.setMinimumHeight(44)
                item.setStyleSheet('padding: 8px 6px; font-size: 12px;')
                item.setAccessibleName(text)
                item.setToolTip(text)
                action_row.addWidget(item,1)
            else:
                item = more_menu.addAction(text)
                item.triggered.connect(callback)
            self.file_actions.append(item)
        self.more_actions = MotionButton('More actions  ···')
        self.more_actions.setMenu(more_menu)
        inner.addWidget(self.more_actions)
        detail.setMinimumHeight(210)
        split.addWidget(detail)
        split.setStretchFactor(0, 1)
        layout.addWidget(split, 1)
        self.assign_button = button("Assign stage…", self.assign_stage)
        row.addWidget(self.assign_button)
        self.update_details()

    def browse_projects(self):
        self.project_views.show()
        self.work_panel.hide()
        self.project_cards.setFocus()

    @staticmethod
    def variant_of(file):
        value = file.get('variant','Unspecified')
        return 'General' if value in ('Unspecified','') else value

    def browse_back(self):
        if not self.work_panel.isVisible():return
        if self.browse_step=='files':
            self.breadcrumb_clicked('stages')
        elif self.browse_step=='stages' and any(self.variant_of(f)!='General' for f in self.files):
            self.breadcrumb_clicked('versions')
        else:self.browse_projects()

    def breadcrumb_clicked(self, target):
        if target == 'projects':
            self.browse_projects()
            return
        if target == 'versions':
            self.selected_variant = self.selected_stage = None
            self.browse_step = 'versions'
        elif target == 'stages':
            self.selected_stage = None
            self.browse_step = 'stages'
        self.filter_files()

    def update_browser(self):
        if not self.project:
            return
        import html
        variants = sorted({self.variant_of(f) for f in self.files},key=indexer.natural)
        if self.selected_variant is not None and self.selected_variant not in variants and not self.scan_pending:
            self.selected_variant = self.selected_stage = None
            self.browse_step = 'versions'
        named = any(v != 'General' for v in variants)
        if self.browse_step == 'versions' and not named and (self.files or not self.scan_pending):
            self.browse_step = 'stages'
        file_mode = self.browse_step == 'files'
        self.choice_cards.setVisible(not file_mode)
        self.file_controls.setVisible(file_mode)
        self.file_split.setVisible(file_mode)
        crumbs = '<a href="projects" style="color:#f3dcff">Projects</a>  ›  '
        crumbs += '<a href="versions" style="color:#f3dcff">'+html.escape(Path(self.project).name)+'</a>'
        if self.selected_variant is not None:
            crumbs += '  ›  <a href="stages" style="color:#f3dcff">'+html.escape(self.selected_variant)+'</a>'
        elif self.browse_step != 'versions':
            crumbs += '  ›  <a href="stages" style="color:#f3dcff">Stages</a>'
        if self.selected_stage is not None:
            crumbs += '  ›  '+STAGES[self.selected_stage]
        self.breadcrumb.setText(crumbs)
        if self.browse_step == 'versions':
            entries = [{'name':v,'path':v,'application':'VERSION','subtitle':f"{sum(self.variant_of(f)==v for f in self.files)} files · Choose version →"} for v in variants]
            self.choice_cards.empty_message = 'Discovering project versions…' if self.scan_pending else 'No working files found in this project.'
        elif self.browse_step == 'stages':
            scoped = [f for f in self.files if self.selected_variant is None or self.variant_of(f)==self.selected_variant]
            entries = []
            for key,title in STAGES.items():
                count=sum(self.stage_store.stage(f,self.stage_document)==key for f in scoped)
                artwork=Path(__file__).resolve().parents[1]/'assets/stage-icons'/(key+'.png')
                entries.append({'name':title,'path':key,'application':'STAGE',
                    'artwork':str(artwork) if artwork.is_file() else None,
                    'subtitle':f'{count} files · Choose stage →'})
        else:
            entries=[]
        self.choice_cards.set_entries(entries)

    def choice_selected(self,index):
        entries=self.choice_cards.entries
        if not 0<=index<len(entries):return
        if self.browse_step == 'versions':
            self.selected_variant=entries[index]['path']
            self.selected_stage=None
            self.browse_step='stages'
        else:
            self.selected_stage=entries[index]['path']
            self.browse_step='files'
        self.file_search.clear()
        self.filter_files()
        reveal_page(self.choice_cards if self.browse_step=='stages' else self.file_split)

    def assign_stage(self):
        files=self.file_cards.selected_files()
        if not files or not self.stage_document.get('writable',False):return
        dialog=QDialog(self)
        dialog.setWindowTitle('Assign production stage')
        layout=QVBoxLayout(dialog)
        layout.addWidget(label(f'Assign a stage to {len(files)} selected file(s).','section'))
        combo=QComboBox()
        for key,title in STAGES.items():combo.addItem(title,key)
        combo.setCurrentIndex(combo.findData(self.stage_store.stage(files[0],self.stage_document)))
        layout.addWidget(combo)
        layout.addWidget(label('Files stay in their existing folders. Labels are shared with the project team.','subtitle',True))
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec()!=QDialog.Accepted:return
        self.apply_stage(files,combo.currentData())

    def apply_stage(self,files,stage):
        store=self.stage_store;project=self.project;expected=self.stage_document.get('fingerprint')
        def saved(document):
            if self.project!=project:return
            self.stage_document=document
            self.filter_files()
            self.status.setText(f'{len(files)} files assigned to {STAGES[stage]}')
            activity('Stage assigned',path=project,stage=stage,count=len(files))
        def failed(message):
            if self.project==project:
                self.stage_document={**self.stage_document,'writable':False}
                self.update_details()
            self.error(message+'\nRefresh the project before assigning again. Check write access to its _TOOLS folder.')
        self.worker(lambda job:store.save([f['path'] for f in files],stage,expected),saved,failed)

    def search_projects(self):
        self.render_projects()
        self.browse_projects()

    def worker(self, fn, done, failure=None):
        job = Worker(fn)
        job.result.connect(done)
        job.failure.connect(failure or self.error)
        job.progress.connect(lambda count, directory: self.status.setText(f"Found {count} files · {directory}"))
        job.finished.connect(lambda: self.finished_job(job))
        self.jobs.append(job)
        self.orb.show()
        self.orb.set_busy(True)
        self.progress_bar.setVisible(not self.settings.data["reduced_motion"])
        self.cancel_button.show()
        job.start()
        return job

    def finished_job(self, job):
        if job in self.jobs:
            self.jobs.remove(job)
        job.deleteLater()
        if not self.jobs:
            self.orb.set_busy(False)
            self.orb.setVisible(self.stack.currentWidget() == self.pages["Home"])
            self.progress_bar.hide()
            self.cancel_button.hide()

    def cancel_jobs(self):
        for job in self.jobs:
            job.cancel.set()
        self.status.setText("Cancelling…")

    def load_projects(self):
        roots = list(self.settings.data["roots"])
        def gather(job):
            result, errors, online = [], [], []
            for root in roots:
                if job.cancel.is_set():
                    break
                try:
                    result.extend(indexer.list_projects(root))
                    online.append(root)
                except OSError as exc:
                    errors.append(str(exc))
            return {"projects": sorted(set(result), key=indexer.natural), "errors": errors, "online": online}
        self.status.setText("Finding projects…")
        self.worker(gather, self.projects_loaded)

    def projects_loaded(self, result):
        if result["online"]:
            self.projects = result["projects"]
            atomic_json(user_dir() / "projects.json", self.projects)
        else:
            self.projects = read_json(user_dir() / "projects.json", [])
        self.project_picker.blockSignals(True)
        self.project_picker.clear()
        self.project_picker.addItem("Choose a project", None)
        for path in self.projects:
            self.project_picker.addItem(Path(path).name, path)
        self.project_picker.blockSignals(False)
        self.storage_label.setText("Relay\nConnected" if result["online"] else "Storage offline\nCached projects")
        self.home_storage.setText((f"{len(self.projects)} projects · Storage connected" if result["online"] else
                                   "Storage offline · Cached projects") + "\nCreative projects and working files")
        self.status.setText(f"{len(self.projects)} projects available" + (" · Some storage unavailable" if result["errors"] else ""))
        for project in self.projects:
            self.artwork.request(project, refresh=True)
        self.render_projects()
        self.update_recent()

    def render_projects(self):
        self.filtered_projects = [p for p in self.projects if self.project_search.text().lower() in Path(p).name.lower()]
        self.project_cards.set_entries([{'name':Path(path).name,'path':path,
            'artwork':self.artwork.request(path),
            'subtitle':'★ Favorite · Explore project →' if path in self.settings.data['favorites'] else 'Explore project →'} for path in self.filtered_projects])

    def project_artwork_loaded(self,path):
        for entry in self.project_cards.entries:
            if entry['path']==path:
                entry['artwork']=self.artwork.paths[path]
                self.project_cards.artwork_pixmaps.pop(entry['artwork'],None)
                self.project_cards.update()
                break
        if path in self.settings.data['recent'][:4]:self.update_recent()

    def open_project(self, path):
        if not path:
            return
        if path != self.project:
            self.file_cards.clear()
            self.selected_variant = None
            self.selected_stage = None
            self.browse_step = "versions"
        self.project = path
        self.project_views.hide()
        self.work_panel.show()
        picker_index = self.project_picker.findData(path)
        if picker_index >= 0:
            self.project_picker.setCurrentIndex(picker_index)
        self.settings.recent(path)
        self.navigate("Projects")
        self.stage_store = StageStore(path)
        self.stage_document = self.stage_store.load(shared=False)
        self.scan_pending = True
        self.breadcrumb.setToolTip(path)
        self.files = indexer.cached(path).get("files", [])
        self.populate_filters()
        self.filter_files()
        self.status.setText("Scanning " + Path(path).name + "…")
        for job in self.jobs:
            job.cancel.set()
        def scan(job):
            result = indexer.scan(path, job.cancel, job.progress.emit)
            try:
                result["stage_document"] = StageStore(path).load()
            except ValueError as exc:
                result["stage_document"] = {**StageStore(path).load(False), 'notice':str(exc)}
                result['errors'].append(str(exc))
            return result
        self.worker(scan,
                    lambda result: self.scan_loaded(result, path))
        self.update_recent()

    def scan_loaded(self, result, path):
        if self.project != path:
            return
        self.files = result["files"]
        self.scan_pending = False
        self.stage_document = result.get("stage_document", self.stage_document)
        self.populate_filters()
        self.filter_files()
        suffix = " · Scan cancelled" if result.get("cancelled") else " · Cached / offline" if result.get("cached") else ""
        working = sum(f.get("kind", "working") == "working" for f in self.files)
        outputs = len(self.files) - working
        self.status.setText(f"{working} working files · {outputs} outputs" + suffix + (f" · {len(result['errors'])} storage notices" if result["errors"] else ""))
        if result["errors"]:
            self.status.setToolTip("\n".join(result["errors"]))

    def populate_filters(self):
        titles = {"application": "All applications", "department": "All departments", "variant": "All variants",
                  "shot": "All shots", "stage": "All stages", "version": "All save revisions"}
        for key, combo in self.filters.items():
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(titles[key], "")
            for value in sorted({f[key] for f in self.files}, key=indexer.natural):
                combo.addItem(value, value)
            index = combo.findData(current)
            combo.setCurrentIndex(max(0, index))
            combo.blockSignals(False)

    def filter_files(self):
        self.file_cards.empty_message = 'No files match these filters. Try another application or clear your search.' if self.project else 'Choose a project above to discover its creative files.'
        search = self.file_search.text().lower()
        self.display_files = [f for f in self.files if f.get("kind", "working") == self.file_kind.currentData()
                              and search in f["relative"].lower()
                              and all(not combo.currentData() or f[key] == combo.currentData() for key, combo in self.filters.items())]
        self.display_files = [f for f in self.display_files
                              if (self.selected_variant is None or self.variant_of(f)==self.selected_variant)
                              and (self.selected_stage is None or self.stage_store.stage(f,self.stage_document)==self.selected_stage)]
        self.file_cards.set_entries(self.display_files)
        self.update_browser()
        self.update_details()

    def selected(self):
        row = self.file_cards.currentRow()
        return self.display_files[row] if 0 <= row < len(self.display_files) else None

    def update_details(self):
        if hasattr(self, "details_panel"):
            reveal_page(self.details_panel)
        file = self.selected()
        self.more_actions.setEnabled(bool(file))
        if hasattr(self,"assign_button"):
            self.assign_button.setEnabled(bool(self.file_cards.selectedItems()) and self.stage_document.get("writable",False))
        for item in self.file_actions:
            item.setEnabled(bool(file))
        if not file:
            self.detail_name.setText("Select a working file")
            self.detail_info.setPlainText("Its details and actions will appear here.")
            self.preview_source=icon('Projects',256).pixmap(256,256)
            self.fit_preview()
            return
        self.detail_name.setText(file["name"])
        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(self.detail_name.font())
        self.detail_name.setText(metrics.elidedText(file["name"], Qt.ElideMiddle, max(180, self.detail_name.width())))
        self.detail_name.setToolTip(file["name"])
        relative = file['path']
        self.detail_info.setPlainText(file["application"] + " · " + file["version"] + "\n" + file["department"] + " · " + STAGES[self.stage_store.stage(file,self.stage_document)]
                                 + "\n" + f"{file['size'] / (1024 * 1024):.1f} MB" + "\n\n" + relative)
        self.detail_info.setToolTip(file["path"])
        pixmap=QPixmap()
        if file.get('preview'):
            from PySide6.QtGui import QImageReader
            reader=QImageReader(file['preview']);reader.setAutoTransform(True)
            size=reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(512,512,Qt.KeepAspectRatio))
                pixmap=QPixmap.fromImage(reader.read())
        self.preview_source=pixmap if not pixmap.isNull() else icon(file['application'],256).pixmap(256,256)
        self.fit_preview()
        self.file_actions[-1].setText("Unfavorite file" if file["path"] in self.settings.data["favorites"] else "Favorite file")
        self.file_actions[2].setEnabled(file["application"] in ("Blender", "Photoshop", "After Effects"))

    def fit_preview(self):
        source=getattr(self,'preview_source',None)
        if source is None or source.isNull():
            return
        dpr=self.preview_image.devicePixelRatioF()
        fitted=source.scaled(int(160*dpr),int(max(8,min(72,self.preview_image.height()-6))*dpr),Qt.KeepAspectRatio,Qt.SmoothTransformation)
        fitted.setDevicePixelRatio(dpr)
        self.preview_image.setPixmap(fitted)

    def open_path(self, path, application=None, executable=None):
        application = application or indexer.EXTENSIONS.get(Path(path).suffix.lower(), "")
        apps.open_file(path, application, self.settings.data["apps"], executable)
        activity("File opened", path=path, application=application)
        self.status.setText("Opened " + Path(path).name)

    def open_selected(self):
        file = self.selected()
        if file:
            try:
                self.open_path(file["path"], file["application"])
            except Exception as exc:
                self.error(str(exc))

    def open_with(self):
        file = self.selected()
        if file:
            exe, _ = QFileDialog.getOpenFileName(self, "Choose an application", r"C:\Program Files", "Applications (*.exe)")
            if exe:
                try:
                    self.open_path(file["path"], file["application"], exe)
                except Exception as exc:
                    self.error(str(exc))

    def reveal_selected(self):
        file = self.selected()
        if file:
            try:
                apps.reveal(file["path"])
            except Exception as exc:
                self.error(str(exc))

    def copy_selected(self):
        file = self.selected()
        if file:
            QApplication.clipboard().setText(file["path"])
            self.status.setText("File path copied")

    def favorite_selected(self):
        file = self.selected()
        if file:
            self.settings.favorite(file["path"])
            self.update_details()

    def save_selected_version(self):
        file = self.selected()
        if not file:
            return
        if self.core and self.core.appPlugin.pluginName == file["application"].replace(" ", ""):
            self.save_current_version()
        else:
            from .integration import launch_integration
            try:
                launch_integration(file["application"], "SaveVersion", expected_source=file["path"])
            except Exception as exc:
                self.error(str(exc))

    def save_current_version(self):
        from .integration import save_version_dialog
        if self.core:
            save_version_dialog(self.core, self)
        else:
            self.error("Use Save new version on a selected working file, or open Neotrix Prism from the active creative application.")

    def native_core(self):
        if self.core is None:
            from .integration import get_core
            self.core = get_core("Standalone")
        if self.project:
            config = Path(self.project) / "00_Pipeline" / "pipeline.json"
            if config.is_file() and str(config).replace("\\", "/") != getattr(self.core, "prismIni", ""):
                self.core.changeProject(str(config))
        return self.core

    def native_browser(self):
        try:
            core = self.native_core()
            from ProjectScripts import ProjectBrowser
            self._native_browser = ProjectBrowser.ProjectBrowser(core=core)
            native_theme(self._native_browser, self.settings.data["theme"] == "dark")
            self._native_browser.setWindowTitle("Neotrix Prism · Managed projects")
            self._native_browser.show()
        except Exception as exc:
            self.error(str(exc))

    def state_manager(self):
        try:
            core = self.native_core()
            manager = core.stateManager()
            if manager:
                native_theme(manager, self.settings.data["theme"] == "dark")
                manager.setWindowTitle("Neotrix Prism · Production tools")
        except Exception as exc:
            self.error(str(exc))

    def native_settings(self):
        try:
            core = self.native_core()
            settings = core.prismSettings()
            if settings:
                native_theme(settings, self.settings.data["theme"] == "dark")
                settings.setWindowTitle("Neotrix Prism · Project settings")
        except Exception as exc:
            self.error(str(exc))

    def build_favorites(self):
        layout = self.page("Favorites")
        self.favorite_table = table(["Project or file", "Path"])
        self.favorite_table.cellDoubleClicked.connect(self.open_favorite)
        layout.addWidget(self.favorite_table)
        actions = QHBoxLayout()
        actions.addWidget(button("Favorite current project", self.favorite_project))
        actions.addWidget(button("Remove selected favorite", self.remove_favorite))
        actions.addStretch()
        layout.addLayout(actions)

    def refresh_favorites(self):
        self.favorite_table.setRowCount(len(self.settings.data["favorites"]))
        for i, path in enumerate(self.settings.data["favorites"]):
            self.favorite_table.setItem(i, 0, QTableWidgetItem(Path(path).name))
            self.favorite_table.setItem(i, 1, QTableWidgetItem(path))

    def favorite_project(self):
        if self.project:
            if self.project not in self.settings.data["favorites"]:
                self.settings.favorite(self.project)
            self.refresh_favorites()
        else:
            self.status.setText("Select a project first.")

    def remove_favorite(self):
        row = self.favorite_table.currentRow()
        if row >= 0:
            self.settings.favorite(self.settings.data["favorites"][row])
            self.refresh_favorites()

    def open_favorite(self, row, column):
        path = self.settings.data["favorites"][row]
        if Path(path).suffix.lower() in {**indexer.EXTENSIONS, **indexer.MEDIA}:
            try:
                self.open_path(path)
            except Exception as exc:
                self.error(str(exc))
        else:
            self.open_project(path)

    def build_activity(self):
        layout = self.page("Activity")
        self.activity_table = table(["Event", "When", "Details"])
        self.activity_table.itemSelectionChanged.connect(self.show_activity)
        layout.addWidget(self.activity_table, 1)
        self.activity_detail = QPlainTextEdit()
        self.activity_detail.setReadOnly(True)
        self.activity_detail.setMaximumHeight(200)
        layout.addWidget(self.activity_detail)

    def refresh_history(self):
        self.records = history()
        self.activity_table.setRowCount(len(self.records))
        for i, record in enumerate(self.records):
            detail = record.get("path", record.get("name", ""))
            for j, value in enumerate((record["event"], time.strftime("%d %b · %H:%M", time.localtime(record["time"])), detail)):
                self.activity_table.setItem(i, j, QTableWidgetItem(value))

    def show_activity(self):
        row = self.activity_table.currentRow()
        if 0 <= row < len(self.records):
            self.activity_detail.setPlainText(json.dumps(self.records[row], indent=2, ensure_ascii=False))

    def build_settings(self):
        layout = self.page("Settings")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form_layout = QVBoxLayout(content)
        frame, inner = card()
        inner.addWidget(label("Connected storage", "section"))
        inner.addWidget(label("One project-library root per line. Existing project folders stay in place.", "subtitle", True))
        self.roots_edit = QPlainTextEdit("\n".join(self.settings.data["roots"]))
        self.roots_edit.setMaximumHeight(85)
        inner.addWidget(self.roots_edit)
        inner.addWidget(button("Add storage folder", self.add_root))
        form_layout.addWidget(frame)
        frame, inner = card()
        inner.addWidget(label("Creative applications", "section"))
        inner.addWidget(label("Detected applications can be changed here. Empty paths use Windows file associations.", "subtitle", True))
        app_form = QFormLayout()
        self.app_fields = {}
        detected = apps.discover()
        for name in ("Blender", "Photoshop", "Illustrator", "After Effects", "Fusion"):
            row = QHBoxLayout()
            field = QLineEdit(self.settings.data["apps"].get(name, detected.get(name, "")))
            self.app_fields[name] = field
            row.addWidget(field, 1)
            row.addWidget(button("Choose", lambda checked=False, f=field: self.choose_executable(f)))
            app_form.addRow(name, row)
        inner.addLayout(app_form)
        form_layout.addWidget(frame)
        frame, inner = card()
        inner.addWidget(label("Look and feel", "section"))
        row = QHBoxLayout()
        self.theme = QComboBox()
        self.theme.addItems(["light", "dark"])
        self.theme.setCurrentText(self.settings.data["theme"])
        row.addWidget(label("Appearance", "subtitle"))
        row.addWidget(self.theme)
        self.reduced = QCheckBox("Reduce motion")
        self.reduced.setChecked(self.settings.data["reduced_motion"])
        row.addWidget(self.reduced)
        row.addStretch()
        inner.addLayout(row)
        form_layout.addWidget(frame)
        form_layout.addWidget(button("Save settings", self.save_settings, True))
        form_layout.addWidget(label("Based on Prism v2.1.3 · Open-source edition\nUpstream upgrades are merged and tested deliberately.", "subtitle"))
        form_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        # Discovery is per-user only; never written into the repository.
        if not self.settings.data["apps"]:
            self.settings.data["apps"] = detected
            self.settings.save()

    def add_root(self):
        root = QFileDialog.getExistingDirectory(self, "Add project-library root")
        if root:
            self.roots_edit.appendPlainText(root)

    def choose_executable(self, field):
        path, _ = QFileDialog.getOpenFileName(self, "Choose executable", r"C:\Program Files", "Application (*.exe)")
        if path:
            field.setText(path)

    def save_settings(self):
        roots = [r.strip() for r in self.roots_edit.toPlainText().splitlines() if r.strip()]
        if not roots:
            self.error("Add at least one project-library root.")
            return
        self.settings.data.update(roots=roots, apps={k: f.text().strip() for k, f in self.app_fields.items()},
                                  theme=self.theme.currentText(), reduced_motion=self.reduced.isChecked())
        self.settings.save()
        self.apply_theme()
        self.load_projects()
        self.status.setText("Settings saved")

    def refresh(self):
        if self.project and self.stack.currentWidget() == self.pages["Projects"]:
            self.open_project(self.project)
        else:
            self.load_projects()

    def error(self, message):
        self.status.setText(message[:150])
        QMessageBox.warning(self, "Neotrix Prism", message)

    def closeEvent(self, event):
        if self.jobs:
            self.cancel_jobs()
            event.ignore()
            QTimer.singleShot(150, self.close)
        else:
            event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self, lambda: self.move_selection(next((n for n, b in self.nav.items() if b.isChecked()), "Home")))

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and hasattr(self, "surface"):
            margin = 0 if self.isMaximized() else 8
            self.shell_layout.setContentsMargins(margin, margin, margin, margin)
            self.surface.update_shape()
            if self.isMinimized():
                self.orb.spin.stop()
            else:
                self.orb.set_busy(bool(self.jobs))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "selection_rail"):
            def align():
                current = next((n for n, b in self.nav.items() if b.isChecked()), "Home")
                self.selection_rail.setGeometry(self.nav[current].geometry())
                if hasattr(self,'preview_image'):
                    self.preview_image.setFixedHeight(44 if self.height()<=760 else 78)
                    self.fit_preview()
                for frame in self.pages["Home"].findChildren(GradientTile):
                    if frame.tone in ("Projects", "Favorites"):
                        for artwork in frame.findChildren(MotionIcon):
                            size = 90 if self.width() <= 1150 else 112
                            artwork.setFixedSize(size, size)
            QTimer.singleShot(0, self, align)
