"""Neotrix's Windows workspace, sharing the same Qt shell with creative integrations."""
import json
import os
import threading
import time
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QStackedWidget, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSplitter, QScrollArea, QProgressBar, QMessageBox, QFileDialog,
    QPlainTextEdit, QCheckBox, QFormLayout, QDialog, QDialogButtonBox, QMenu, QLayout)
from . import __version__, apps, indexer, graph
from .storage import Settings, GraphLibrary, user_dir, atomic_json, read_json, history, activity
from .design import icon, stylesheet, fade, palette, native_theme
from .surfaces import Atmosphere, GradientTile, WorkspaceArt
from .motion import MotionButton, MotionIcon, OrbButton, reveal_page, tween, enabled
from .window_chrome import RoundedShell, Caption, ResizeFrame
from .graph_ui import GraphEditor


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
        for name in ("Home", "Projects", "Favorites", "Workflows", "Activity", "Settings"):
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
        footer = QHBoxLayout()
        self.status = label("Ready", "subtitle")
        footer.addWidget(self.status, 1)
        self.orb = OrbButton()
        self.orb.clicked.connect(lambda: self.cancel_jobs() if self.jobs else self.navigate("Projects"))
        footer.addWidget(self.orb)
        footer.addStretch(1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.hide()
        footer.addWidget(self.progress_bar)
        self.cancel_button = button("Cancel", self.cancel_jobs)
        self.cancel_button.hide()
        footer.addWidget(self.cancel_button)
        body.addLayout(footer)
        layout.addWidget(content, 1)
        self.build_home()
        self.build_projects()
        self.build_favorites()
        self.build_workflows()
        self.build_activity()
        self.build_settings()
        self.apply_theme()
        self.resize_frame = ResizeFrame(self)
        refresh = QAction(self)
        refresh.setShortcut(QKeySequence.Refresh)
        refresh.triggered.connect(self.refresh)
        self.addAction(refresh)
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
        self.editor.dark = dark
        self.editor.view.viewport().update()
        for item in self.editor.items.values():
            if self.settings.data["reduced_motion"]:
                animation = getattr(item, "_glow", None)
                if animation:
                    animation.stop()
                item.set_glow(0)
            item.update()
        for widget in self.findChildren(MotionIcon):
            if not enabled(widget):
                for key in ("_hover", "_reveal"):
                    animation = getattr(widget, key, None)
                    if animation:
                        animation.stop()
                widget.set_hover(0)
                widget.set_reveal(1)
        self.orb.set_busy(bool(self.jobs))

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

    def navigate(self, name):
        titles = {"Home": ("Your creative workspace", "Everything you need to pick up where you left off."),
                  "Projects": ("Projects", "Find the right project. Open the right version."),
                  "Favorites": ("Your favorites", "The projects and files you keep close."),
                  "Workflows": ("Make work flow", "Connect simple steps. Preview changes. Run when you're ready."),
                  "Activity": ("Your activity", "A clear record of files opened, versions saved and workflows run."),
                  "Settings": ("Make it yours", "Storage, applications and the way your workspace feels.")}
        self.page_title.setText(titles[name][0])
        self.page_subtitle.setText(titles[name][1])
        self.page_title.setAlignment(Qt.AlignCenter if name == "Home" else Qt.AlignLeft)
        self.page_subtitle.setAlignment(Qt.AlignCenter if name == "Home" else Qt.AlignLeft)
        for key, nav in self.nav.items():
            nav.setChecked(key == name)
        self.stack.setCurrentWidget(self.pages[name])
        self.orb.setVisible(name == "Home" or bool(self.jobs))
        QTimer.singleShot(0, self, lambda: self.move_selection(name))
        if name == "Activity":
            self.refresh_history()
        elif name == "Favorites":
            self.refresh_favorites()
        elif name == "Workflows":
            self.editor.refresh_library()
            QTimer.singleShot(0, self.editor.fit)
        reveal_page(self.pages[name])
        if name == "Home":
            for i, artwork in enumerate(self.pages[name].findChildren(MotionIcon)):
                artwork.appear(i * 75)

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
            ("Workflows", "Make work flow", "Collect and open files with reusable visual workflows."),
            ("Favorites", "Your best, on hand", "Keep favorite projects and files one click away."))):
            frame = GradientTile(name)
            inner = QVBoxLayout(frame)
            inner.setContentsMargins(22, 18, 22, 20)
            inner.setSpacing(10)
            top = QHBoxLayout()
            top.addWidget(label({"Projects": "PROJECT LIBRARY", "Workflows": "VISUAL WORKFLOWS", "Favorites": "FAVORITES"}[name], "eyebrow", True), 1)
            item = MotionIcon(name, 112)
            top.addWidget(item)
            inner.addLayout(top)
            inner.addWidget(label(title, "section", True))
            inner.addWidget(label(description, "subtitle", True))
            inner.addStretch()
            inner.addWidget(button("Open " + name.lower(), lambda checked=False, n=name: self.navigate(n)))
            overview.addWidget(frame, 100)
            frame.hover_changed.connect(lambda value, i=tile_index: overview.setStretch(i, int(100 + 12 * value)))
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
            item.setIcon(icon("Projects", 38))
            item.setIconSize(QSize(38, 38))
            self.recent_grid.addWidget(item, i // 2, i % 2)
        if not self.settings.data["recent"]:
            self.recent_grid.addWidget(label("Open a project to see it here.", "subtitle"), 0, 0)

    def build_projects(self):
        layout = self.page("Projects")
        project_controls = QHBoxLayout()
        self.project_search = QLineEdit()
        self.project_search.setPlaceholderText("Search projects")
        self.project_search.textChanged.connect(self.render_projects)
        project_controls.addWidget(self.project_search, 1)
        self.project_picker = QComboBox()
        self.project_picker.setMinimumWidth(160)
        self.project_picker.activated.connect(lambda i: self.open_project(self.project_picker.itemData(i)))
        project_controls.addWidget(self.project_picker)
        self.project_mode = QComboBox()
        self.project_mode.addItems(["Cards", "List"])
        self.project_mode.currentIndexChanged.connect(self.render_projects)
        project_controls.addWidget(self.project_mode)
        project_controls.addWidget(button("Browse projects", lambda: self.project_views.setVisible(not self.project_views.isVisible())))
        project_controls.addWidget(button("Refresh", self.refresh))
        layout.addLayout(project_controls)
        self.project_views = QStackedWidget()
        self.project_cards = QScrollArea()
        self.project_cards.setWidgetResizable(True)
        self.project_grid_widget = QWidget()
        self.project_grid = QGridLayout(self.project_grid_widget)
        self.project_grid.setContentsMargins(0, 0, 0, 0)
        self.project_cards.setWidget(self.project_grid_widget)
        self.project_views.addWidget(self.project_cards)
        self.project_table = table(["Project", "Storage", "Favorite"])
        self.project_table.cellDoubleClicked.connect(lambda row, col: self.open_project(self.filtered_projects[row]))
        self.project_views.addWidget(self.project_table)
        self.project_views.setMaximumHeight(210)
        self.project_views.setMinimumHeight(135)
        layout.addWidget(self.project_views)
        self.breadcrumb = label("Select a project to explore its working files.", "subtitle")
        self.breadcrumb.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.breadcrumb)
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
        layout.addLayout(row)
        row = QHBoxLayout()
        for key, title in (("variant", "All variants"), ("shot", "All shots"), ("stage", "All stages"), ("version", "All versions")):
            combo = QComboBox()
            combo.addItem(title, "")
            combo.currentIndexChanged.connect(self.filter_files)
            row.addWidget(combo, 1)
            self.filters[key] = combo
        layout.addLayout(row)
        split = QSplitter()
        self.file_table = table(["Working file", "Application", "Version", "Modified"])
        self.file_table.itemSelectionChanged.connect(self.update_details)
        self.file_table.cellDoubleClicked.connect(lambda row, col: self.open_selected())
        split.addWidget(self.file_table)
        detail, inner = card()
        self.details_panel = detail
        detail.setMinimumWidth(220)
        detail.setMaximumWidth(280)
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setMinimumHeight(100)
        self.preview_image.setFixedHeight(115)
        inner.addWidget(self.preview_image)
        self.detail_name = label("Select a working file", "section", True)
        inner.addWidget(self.detail_name)
        self.detail_info = label("Its details and actions will appear here.", "subtitle", True)
        self.detail_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        inner.addWidget(self.detail_info)
        inner.addStretch()
        self.file_actions = []
        for text, callback, primary in (("Open file", self.open_selected, True), ("Open with…", self.open_with, False),
                                         ("Save new version", self.save_selected_version, False),
                                         ("Reveal in Explorer", self.reveal_selected, False), ("Copy path", self.copy_selected, False),
                                         ("Favorite file", self.favorite_selected, False)):
            item = button(text, callback, primary)
            inner.addWidget(item)
            self.file_actions.append(item)
        detail.setMinimumHeight(620)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(detail)
        detail_scroll.setMinimumWidth(230)
        detail_scroll.setMaximumWidth(285)
        split.addWidget(detail_scroll)
        split.setStretchFactor(0, 1)
        layout.addWidget(split, 1)
        self.update_details()

    def worker(self, fn, done, failure=None):
        job = Worker(fn)
        job.result.connect(done)
        job.failure.connect(failure or self.error)
        job.progress.connect(lambda count, directory: self.status.setText(f"Found {count} files · {directory}"))
        job.node.connect(self.editor.set_node_state)
        job.finished.connect(lambda: self.finished_job(job))
        self.jobs.append(job)
        self.orb.show()
        self.orb.set_busy(True)
        self.progress_bar.show()
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
        self.workflow_project.clear()
        self.workflow_project.addItem("Choose a project", None)
        for path in self.projects:
            self.workflow_project.addItem(Path(path).name, path)
        self.storage_label.setText("Relay\nConnected" if result["online"] else "Storage offline\nCached projects")
        self.home_storage.setText((f"{len(self.projects)} projects · Storage connected" if result["online"] else
                                   "Storage offline · Cached projects") + "\nShared files and reusable workflows")
        self.status.setText(f"{len(self.projects)} projects available" + (" · Some storage unavailable" if result["errors"] else ""))
        self.render_projects()
        self.update_recent()

    def render_projects(self):
        self.filtered_projects = [p for p in self.projects if self.project_search.text().lower() in Path(p).name.lower()]
        self.project_views.setCurrentIndex(self.project_mode.currentIndex())
        self.clear_layout(self.project_grid)
        self.project_table.setRowCount(len(self.filtered_projects))
        for i, path in enumerate(self.filtered_projects):
            item = button(Path(path).name + "\nExplore project  →", lambda checked=False, p=path: self.open_project(p))
            item.setObjectName("projectCard")
            item.setMinimumHeight(110)
            item.setIcon(icon("Projects", 40))
            item.setIconSize(QSize(40, 40))
            item.setToolTip(path)
            self.project_grid.addWidget(item, i // 3, i % 3)
            for j, text in enumerate((Path(path).name, str(Path(path).parent),
                                      "★" if path in self.settings.data["favorites"] else "")):
                self.project_table.setItem(i, j, QTableWidgetItem(text))
        if not self.filtered_projects:
            self.project_grid.addWidget(label("No projects found. Check storage roots in Settings.", "subtitle"), 0, 0)
        self.project_grid.setRowStretch(len(self.filtered_projects) // 3 + 1, 1)

    def open_project(self, path):
        if not path:
            return
        self.project = path
        self.project_views.hide()
        picker_index = self.project_picker.findData(path)
        if picker_index >= 0:
            self.project_picker.setCurrentIndex(picker_index)
        workflow_index = self.workflow_project.findData(path)
        if workflow_index >= 0:
            self.workflow_project.setCurrentIndex(workflow_index)
        self.settings.recent(path)
        self.navigate("Projects")
        self.breadcrumb.setText(Path(path).name + "  /  Working files")
        self.breadcrumb.setToolTip(path)
        self.files = indexer.cached(path).get("files", [])
        self.populate_filters()
        self.filter_files()
        self.status.setText("Scanning " + Path(path).name + "…")
        for job in self.jobs:
            job.cancel.set()
        self.worker(lambda job: indexer.scan(path, job.cancel, job.progress.emit),
                    lambda result: self.scan_loaded(result, path))
        self.update_recent()

    def scan_loaded(self, result, path):
        if self.project != path:
            return
        self.files = result["files"]
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
                  "shot": "All shots", "stage": "All stages", "version": "All versions"}
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
        search = self.file_search.text().lower()
        self.display_files = [f for f in self.files if f.get("kind", "working") == self.file_kind.currentData()
                              and search in f["relative"].lower()
                              and all(not combo.currentData() or f[key] == combo.currentData() for key, combo in self.filters.items())]
        self.file_table.setRowCount(len(self.display_files))
        for i, file in enumerate(self.display_files):
            texts = [file["name"], file["application"], file["version"],
                     time.strftime("%d %b %Y · %H:%M", time.localtime(file["modified"]))]
            for j, text in enumerate(texts):
                item = QTableWidgetItem(text)
                item.setToolTip(file["path"])
                if j == 0:
                    item.setIcon(icon(file["application"], 28))
                self.file_table.setItem(i, j, item)
        self.update_details()

    def selected(self):
        row = self.file_table.currentRow()
        return self.display_files[row] if 0 <= row < len(self.display_files) else None

    def update_details(self):
        if hasattr(self, "details_panel"):
            reveal_page(self.details_panel)
        file = self.selected()
        for item in self.file_actions:
            item.setEnabled(bool(file))
        if not file:
            self.detail_name.setText("Select a working file")
            self.detail_info.setText("Its details and actions will appear here.")
            self.preview_image.setPixmap(icon("Projects", 82).pixmap(82, 82))
            return
        self.detail_name.setText(file["name"])
        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(self.detail_name.font())
        self.detail_name.setText(metrics.elidedText(file["name"], Qt.ElideMiddle, max(180, self.detail_name.width())))
        self.detail_name.setToolTip(file["name"])
        relative = QFontMetrics(self.detail_info.font()).elidedText(file["relative"], Qt.ElideMiddle, max(180, self.detail_info.width()))
        self.detail_info.setText(file["application"] + " · " + file["version"] + "\n" + file["department"] + " · " + file["stage"]
                                 + "\n" + f"{file['size'] / (1024 * 1024):.1f} MB" + "\n\n" + relative)
        self.detail_info.setToolTip(file["path"])
        pixmap = QPixmap(file["preview"]) if file.get("preview") else QPixmap()
        self.preview_image.setPixmap(pixmap.scaled(218, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation) if not pixmap.isNull()
                                     else icon(file["application"], 90).pixmap(90, 90))
        self.file_actions[-1].setText("Unfavorite file" if file["path"] in self.settings.data["favorites"] else "Favorite file")
        self.file_actions[2].setEnabled(file["application"] in ("Blender", "Photoshop", "After Effects"))

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

    def build_workflows(self):
        layout = self.page("Workflows")
        row = QHBoxLayout()
        self.workflow_project = QComboBox()
        row.addWidget(label("Project context", "subtitle"))
        row.addWidget(self.workflow_project, 1)
        self.workflow_project.setMinimumWidth(240)
        layout.addLayout(row)
        self.editor = GraphEditor(self.settings.data["graph_root"])
        self.editor.preview_requested.connect(self.preview_graph)
        layout.addWidget(self.editor, 1)

    def preview_graph(self, document):
        if not self.editor.library.online():
            self.editor.refresh_library()
            self.error("Reconnect the shared workflow library before previewing or running workflows.")
            return
        path = self.workflow_project.currentData() or self.project
        if not path:
            self.error("Choose a project context before previewing a workflow.")
            return
        self.editor.run_button.setEnabled(False)
        def done(preview):
            self.editor.run_button.setEnabled(True)
            self.preview = preview
            dialog = QDialog(self)
            dialog.setWindowTitle("Review workflow changes")
            dialog.resize(820, 540)
            layout = QVBoxLayout(dialog)
            layout.addWidget(label("Ready when you are.", "title"))
            layout.addWidget(label("These are the file changes and application launches this workflow will perform.", "subtitle", True))
            text = QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText("\n".join(self.describe_action(a) for a in preview["actions"]) or "This graph has no file-changing actions.")
            layout.addWidget(text, 1)
            buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
            run = buttons.addButton("Run workflow", QDialogButtonBox.AcceptRole)
            run.setObjectName("primary")
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if dialog.exec() == QDialog.Accepted:
                self.run_graph(preview)
        def failure(message):
            self.editor.run_button.setEnabled(True)
            self.error(message)
        self.worker(lambda job: graph.plan(document, path, job.cancel, job.progress.emit), done, failure)

    @staticmethod
    def describe_action(action):
        kind = action["kind"]
        if kind == "copy":
            return ("SKIP existing" if action.get("skip") else "COPY") + "  " + action["source"] + "\n     → " + action["destination"]
        if kind == "mkdir":
            return "CREATE FOLDER  " + action["destination"]
        if kind == "open":
            return "OPEN  " + action["source"]
        return "LOG  " + action["message"] + f" ({action['count']} files)"

    def run_graph(self, preview):
        if not self.editor.library.online():
            self.editor.refresh_library()
            self.error("The shared workflow library disconnected after preview. Reconnect before running.")
            return
        self.editor.run_button.setEnabled(False)
        configured = dict(self.settings.data["apps"])
        def run(job):
            return graph.execute(preview, lambda path: apps.open_file(path, indexer.EXTENSIONS.get(Path(path).suffix.lower(), ""), configured),
                                 job.cancel, job.node.emit)
        def done(records):
            self.editor.run_button.setEnabled(True)
            activity("Workflow run", name=preview["graph"]["name"], records=records)
            self.status.setText(f"Workflow finished · {len(records)} actions recorded")
            self.navigate("Activity")
        def failure(message):
            self.editor.run_button.setEnabled(True)
            self.error(message)
        self.worker(run, done, failure)

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
        inner.addWidget(label("Shared workflow-library root", "subtitle"))
        self.graph_root_edit = QLineEdit(self.settings.data["graph_root"])
        inner.addWidget(self.graph_root_edit)
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
        if not self.graph_root_edit.text().strip():
            self.error("Set a shared workflow-library root.")
            return
        self.settings.data.update(roots=roots, graph_root=self.graph_root_edit.text().strip(), apps={k: f.text().strip() for k, f in self.app_fields.items()},
                                  theme=self.theme.currentText(), reduced_motion=self.reduced.isChecked())
        self.settings.save()
        self.editor.library = GraphLibrary(self.settings.data["graph_root"])
        self.editor.refresh_library()
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
        current_project = self.workflow_project.currentData()
        self.workflow_project.blockSignals(True)
        self.workflow_project.clear()
        self.workflow_project.addItem("Choose a project", None)
        for path in self.projects:
            self.workflow_project.addItem(Path(path).name, path)
        if current_project:
            self.workflow_project.setCurrentIndex(max(0, self.workflow_project.findData(current_project)))
        self.workflow_project.blockSignals(False)
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
                for frame in self.pages["Home"].findChildren(GradientTile):
                    if frame.tone in ("Projects", "Workflows", "Favorites"):
                        for artwork in frame.findChildren(MotionIcon):
                            size = 90 if self.width() <= 1150 else 112
                            artwork.setFixedSize(size, size)
            QTimer.singleShot(0, self, align)
