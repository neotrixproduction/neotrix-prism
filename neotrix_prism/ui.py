"""Neotrix's Windows workspace, sharing the same Qt shell with creative integrations."""
import json
import os
import threading
import time
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QRect, QPoint, QPointF
from PySide6.QtGui import QPixmap, QIcon, QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QStackedWidget, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSplitter, QScrollArea, QProgressBar, QMessageBox, QFileDialog,
    QPlainTextEdit, QCheckBox, QFormLayout, QDialog, QDialogButtonBox, QMenu, QLayout, QSizePolicy, QAbstractScrollArea, QSlider, QInputDialog)
from . import __version__, apps, indexer
from .storage import Settings, user_dir, atomic_json, read_json, history, activity
from .design import icon, stylesheet, fade, palette, native_theme, search_icon
from . import physics
from .ambient import Ambient
from .surfaces import Atmosphere, GradientTile
from .motion import MotionButton, MotionIcon, OrbButton, SceneTransition, reveal_page, cascade, snapshot, spring, enabled, motion_blocks, ripple_blocks, SmoothWheel
from .choreo import KineticLabel, Shockwave, ZoomThrough, StatusLine, Hairline
from .window_chrome import RoundedShell, Caption, ResizeFrame
from .project_browser import GridCards, FileList, ActivityList, ProjectArtwork
from .project_metadata import StageStore, STAGES, STAGE_NOTES, ALL_STAGES, stage_folder
from .cards import CardSurface, round_surface
from .sound import SoundEngine


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


def plural(count, word):
    return f"{count} {word}" + ("" if count == 1 else "s")


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
        # Soft spatial cues timed to the motion; silent when muted or unavailable.
        self.sound = SoundEngine(self)
        self._refresh_cue = None
        self.projects, self.files, self.display_files, self.jobs = [], [], [], []
        self.project, self.preview = None, None
        self.project_section = 'work'
        self.selected_area = None
        self.selected_collection = None
        self.setWindowTitle("Neotrix Prism")
        self.setObjectName("workspaceWindow")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1]/'assets/neotrix.ico')))
        self.resize(1360, 900)
        self.setMinimumSize(1024, 720)
        shell = RoundedShell()
        self.setCentralWidget(shell)
        self.shell_layout = QVBoxLayout(shell)
        self.shell_layout.setContentsMargins(8, 8, 8, 8)
        self.shell_layout.setSpacing(0)
        self.surface = Atmosphere()
        self.shell_layout.addWidget(self.surface)
        # One shared idle clock keeps colour and artwork alive while the app is in use.
        self.ambient = Ambient(self)
        self.ambient.subscribe(self.surface, 3)
        self._wave_origin = None
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
        self.compact_sidebar = True
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(76)
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(10, 18, 10, 16)
        nav_layout.setSpacing(8)
        brand = QHBoxLayout()
        brand.setSpacing(6)
        mark = MotionIcon('Brand', 32)
        brand.addWidget(mark, 0, Qt.AlignVCenter)
        self.brand_label = label("Neotrix Prism")
        self.brand_label.setObjectName('sidebarBrand')
        self.brand_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.brand_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.brand_label.hide()
        brand.addWidget(self.brand_label, 1)
        nav_layout.addLayout(brand)
        nav_layout.addSpacing(22)
        self.nav = {}
        for name in ("Projects", "Favorites", "Activity", "Settings"):
            item = button('', lambda checked=False, n=name: self.navigate(n))
            item.setObjectName("nav")
            item.setCheckable(True)
            item.setToolTip(name)
            item.setAccessibleName(name)
            item.setMinimumHeight(52)
            item.setIcon(icon('Navigation'+name, 64))
            item.setIconSize(QSize(24, 24))
            nav_layout.addWidget(item)
            self.nav[name] = item
        nav_layout.addStretch()
        self.version_label = label("v" + __version__, "subtitle")
        self.version_label.setStyleSheet('font-size:10px; color:rgba(232,224,248,100); background:transparent;')
        nav_layout.addWidget(self.version_label)
        self.version_label.hide()
        self.selection_rail = QFrame(sidebar)
        self.selection_rail.setObjectName("selectionRail")
        self.selection_rail.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.selection_rail.lower()
        layout.addWidget(sidebar)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(28, 12, 28, 8)
        body.setSpacing(12)
        header = QHBoxLayout()
        left = QVBoxLayout()
        self.page_title = KineticLabel("Your creative workspace")
        self.page_title.setObjectName("title")
        self.page_subtitle = label("Everything you need to pick up where you left off.", "subtitle")
        left.addWidget(self.page_title)
        left.addWidget(self.page_subtitle)
        self.page_subtitle.hide()
        header.addLayout(left, 1)
        body.addLayout(header)
        self.stack = QStackedWidget()
        self.pages = {}
        body.addWidget(self.stack, 1)
        footer_host = QWidget()
        # The orb's transparent canvas must fit inside its parent too; otherwise
        # Qt clips the hover halo and busy rings at the footer boundary.
        footer_host.setFixedHeight(112)
        footer = QGridLayout(footer_host)
        footer.setContentsMargins(0,0,0,0)
        footer.setColumnStretch(0,1)
        footer.setColumnStretch(2,1)
        # Status lines roll in quickly; rapid progress updates swap instantly.
        # One quiet line: elided in the middle, full text in its tooltip.
        self.status = StatusLine("Ready")
        self.status.setObjectName("statusLine")
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        footer.addWidget(self.status,0,0)
        self.orb = OrbButton()
        self.surface.palette_changed.connect(self.orb.update)
        self.ambient.subscribe(self.orb, 2)
        self.orb.clicked.connect(lambda: self.cancel_jobs() if self.jobs else self.refresh())
        orb_policy = self.orb.sizePolicy()
        orb_policy.setRetainSizeWhenHidden(True)
        self.orb.setSizePolicy(orb_policy)
        footer.addWidget(self.orb,0,1,Qt.AlignCenter)
        task_controls = QWidget()
        task_controls.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        task_layout = QHBoxLayout(task_controls)
        task_layout.setContentsMargins(0,0,0,0)
        task_layout.addStretch()
        # Work in progress reads as a thin line of light, not a bar.
        self.progress_bar = Hairline()
        task_layout.addWidget(self.progress_bar, 0, Qt.AlignVCenter)
        self.cancel_button = button("Cancel", self.cancel_jobs)
        self.cancel_button.setObjectName("quietAction")
        self.cancel_button.hide()
        task_layout.addWidget(self.cancel_button)
        footer.addWidget(task_controls,0,2)
        body.addWidget(footer_host)
        layout.addWidget(content, 1)
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
        self.wire_sound()
        self.navigate("Projects")
        self.load_projects()

        from .updater import portable_root
        if portable_root(Path(__file__).resolve().parents[1]) and not os.environ.get('PYTEST_CURRENT_TEST') and not os.environ.get('NEOTRIX_DISABLE_UPDATE_CHECK'):
            QTimer.singleShot(3500,self,lambda:self.updates.check_now(automatic=True))

    def wire_sound(self):
        """Buttons click and breathe on hover; cards and rows answer the pointer
        with a note placed where they sit on screen."""
        self.orb.silent_press = True  # the orb answers with the refresh or cancel cue instead
        self.sound.wire(self)
        for grid in (self.project_cards, self.choice_cards, self.favorite_cards):
            grid.hovered.connect(lambda index, grid=grid: self.card_hover(grid, index))
            grid.pressed.connect(lambda index: self.sound.play('press-card'))
        for rows in (self.file_cards, self.activity_list):
            rows.hovered.connect(lambda row: self.sound.play('hover-soft', hover=True))
            rows.itemSelectionChanged.connect(lambda rows=rows: rows.selectedItems() and self.sound.play('select'))

    def card_hover(self, grid, index):
        rect = grid.card_rects().get(index)
        if rect is not None and self.isActiveWindow():
            self.sound.at('hover', self.screen_x(grid, rect.center().toPoint()), hover=True)

    def screen_x(self, widget, point):
        """Horizontal position of a widget point across the window, 0..1 (for stereo placement)."""
        return widget.mapTo(self, point).x()/max(1, self.width())

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
            # Springs snap to their destinations so nothing is left mid-flight.
            physics.settle()
            self.ambient.stop()
            zoom = getattr(self, '_zoom', None)
            if zoom:
                zoom.finish()
                self._zoom = None
            for label in self.findChildren(KineticLabel):
                label.stop()
            for widget in self.findChildren(QWidget):
                if widget.graphicsEffect():
                    widget.setGraphicsEffect(None)
            self.sidebar.setFixedWidth(76 if self.compact_sidebar else 180)
        self.settings.data['theme'] = 'dark'
        dark = True
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
                if hasattr(surface,'play_entrance'):surface.entrance_elapsed=-1.0
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
                widget.reset_wave()
        if self.settings.data['reduced_motion']:
            self.surface.reset_wave()
            self.surface.intro = 1.0
            for layer in self.findChildren(Shockwave):
                layer.reset_wave()
            for surface in self.findChildren(GridCards)+self.findChildren(FileList):
                surface.reset_wave()
            for tile in self.findChildren(GradientTile):
                tile.reset_wave()
            for item in self.findChildren(MotionButton):
                item.reset_wave()
        self.orb.set_busy(bool(self.jobs))
        self.progress_bar.set_active(bool(self.jobs) and not self.settings.data["reduced_motion"])

    def move_selection(self, name):
        """The rail's two ends travel on different springs: the leading edge
        darts ahead, the trailing edge follows, so the pill stretches in flight
        and snaps back to size as it lands."""
        target = self.nav[name].geometry()
        self.rail_target = name
        if not enabled(self) or not self.selection_rail.isVisible():
            for edge in ('top', 'bottom'):
                physics.cancel(self, ('rail', edge))
            self.rail_edges = [float(target.top()), float(target.bottom()+1)]
            self.selection_rail.setGeometry(target)
            self.selection_rail.show()
            return
        current = self.selection_rail.geometry()
        self.rail_edges = list(getattr(self, 'rail_edges', [float(current.top()), float(current.bottom()+1)]))
        downward = target.top() > self.rail_edges[0]
        lead, trail = (.24, .8), (.46, .86)
        def place(edge, value):
            self.rail_edges[edge] = value
            column = self.nav[self.rail_target].geometry()
            top, bottom = sorted(self.rail_edges)
            self.selection_rail.setGeometry(column.x(), round(top), column.width(), max(8, round(bottom-top)))
        spring(self, ('rail', 'top'), float(target.top()), lambda v: place(0, v), value=self.rail_edges[0],
               feel=trail if downward else lead, precision=.1)
        spring(self, ('rail', 'bottom'), float(target.bottom()+1), lambda v: place(1, v), value=self.rail_edges[1],
               feel=lead if downward else trail, precision=.1)

    def toggle_sidebar(self):
        self.compact_sidebar = not self.compact_sidebar
        for name, item in self.nav.items():
            item.setText("" if self.compact_sidebar else name)
        self.brand_label.setVisible(not self.compact_sidebar)
        self.version_label.setVisible(not self.compact_sidebar)
        self.caption.collapse.setText("›" if self.compact_sidebar else "‹")
        def step(value):
            self.sidebar.setFixedWidth(int(round(value)))
            current = next((name for name, item in self.nav.items() if item.isChecked()), "Projects")
            if not physics.get(self, ('rail', 'top')):
                self.selection_rail.setGeometry(self.nav[current].geometry())
        spring(self, 'sidebar', 76 if self.compact_sidebar else 180, step, value=self.sidebar.width(),
               feel=(.4, .84), precision=.2)
        self.sound.play('sidebar-close' if self.compact_sidebar else 'sidebar-open')
        if not self.compact_sidebar:
            for label in (self.brand_label, self.version_label):
                reveal_page(label, 80, 10)

    def scene(self, index):
        """Change the workspace colour scene; it floods outward from the control
        the user just used when there is one."""
        self.surface.focus_scene(index, self._wave_origin)

    def project_scene(self, project):
        """A dark scene in the hue of a project's own artwork."""
        return self.art_scene(self.artwork.paths.get(project) or self.artwork.request(project))

    def stage_artwork(self, key):
        return self.asset('stage-icons', key+'.png')

    def art_scene(self, path):
        """A dark three-colour scene in the hue of an artwork."""
        from . import art3d
        from PySide6.QtGui import QColor
        scenes = self.__dict__.setdefault('_project_scenes', {})
        if path not in scenes:
            hue = art3d.dominant(QPixmap(path).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)).hsvHueF() % 1.0
            scenes[path] = (QColor.fromHsvF(hue, .8, .27), QColor.fromHsvF((hue+.05) % 1.0, .74, .17),
                            QColor.fromHsvF((hue+.1) % 1.0, .58, .1))
        return scenes[path]

    def projects_title(self):
        """The page title follows the browsing level, so every step in or out
        gets its own kinetic title change."""
        if not self.project or not self.work_panel.isVisible():
            return "Projects"
        if getattr(self, 'browse_step', None) == 'files' and self.project_section in ('assets','preview'):
            categories=indexer.CLIENT_CATEGORIES if self.project_section=='assets' else indexer.PREVIEW_GROUPS
            return categories.get(self.selected_collection,{'assets':'Assets','preview':'Preview'}[self.project_section])
        if getattr(self, 'browse_step', None) == 'files' and self.selected_stage:
            return 'All stages' if self.selected_stage == ALL_STAGES else STAGES[self.selected_stage]
        if getattr(self,'browse_step',None)=='files' and self.project_section=='work' and self.selected_area:
            return indexer.WORK_AREAS[self.selected_area]
        return Path(self.project).name

    def projects_scene(self):
        """Scene for the Projects page at its current browsing level: the library
        is indigo, a project takes its artwork's hue, a stage its own colour."""
        if not self.project or not self.work_panel.isVisible():
            return 1
        if getattr(self, 'browse_step', None) == 'files' and self.selected_stage and self.selected_stage != ALL_STAGES:
            return self.art_scene(self.stage_artwork(self.selected_stage))
        return self.project_scene(self.project)

    def wave_from(self, widget, point=None):
        centre = point if point is not None else widget.rect().center()
        self._wave_origin = QPointF(widget.mapTo(self.surface, centre))

    def navigate(self, name, origin=None):
        previous = self.stack.currentWidget()
        old_transition = getattr(self, '_scene_transition', None)
        if old_transition:
            old_transition.finish()
            self._scene_transition = None
        outgoing = snapshot(previous) if previous and previous is not self.pages[name] and enabled(self) and self.isVisible() else None
        direction = 1 if previous is None or self.stack.indexOf(previous) <= self.stack.indexOf(self.pages[name]) else -1
        titles = {"Projects": ("Projects", "Find the right project. Open the right version."),
                  "Favorites": ("Favorites", ""),
                  "Activity": ("Activity", ""),
                  "Settings": ("Settings", "")}
        self.page_title.setText(self.projects_title() if name == "Projects" else titles[name][0])
        self.page_subtitle.setText(titles[name][1])
        self.page_title.show()
        self.caption.title.setText('')
        self.page_title.setAlignment(Qt.AlignCenter)
        self.page_subtitle.setAlignment(Qt.AlignCenter)
        for key, nav in self.nav.items():
            nav.setChecked(key == name)
        if previous is not None and previous is not self.pages[name] and enabled(self):
            self.nav[name].hop()
        if previous is not None and previous is not self.pages[name]:
            # Air follows the old page out; the new page arrives on its own interval.
            self.sound.play('nav-whoosh-down' if direction > 0 else 'nav-whoosh-up')
            self.sound.play('nav-'+name.lower(), delay=90)
        self.stack.setCurrentWidget(self.pages[name])
        scene = self.projects_scene() if name == "Projects" else {"Favorites": 2, "Activity": 3, "Settings": 4}[name]
        if previous is not None and previous is not self.pages[name]:
            # The new page's colour floods out from the sidebar item that was chosen.
            self.wave_from(self.nav[name])
        self.scene(scene)
        self._wave_origin = None
        self.orb.show()
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
        elif previous is not self.pages[name]:
            cascade(self.pages[name])

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def build_projects(self):
        layout = self.page("Projects")
        project_controls = QHBoxLayout()
        self.project_search = QLineEdit()
        self.project_search.setPlaceholderText("Search projects")
        self.project_search.addAction(search_icon(), QLineEdit.LeadingPosition)
        self.project_search.textChanged.connect(self.search_projects)
        project_controls.addWidget(self.project_search, 1)
        self.project_picker = QComboBox()
        self.project_picker.setMinimumWidth(160)
        self.project_picker.hide()
        self.project_picker.activated.connect(lambda i: self.open_project(self.project_picker.itemData(i)))
        project_controls.addWidget(self.project_picker)
        # Back only exists where there is somewhere to go back to.
        self.back_button = button("‹  Back", self.browse_back)
        self.back_button.setToolTip("Back (Alt+Left)")
        self.back_button.hide()
        project_controls.insertWidget(0, self.back_button)
        layout.addLayout(project_controls)
        self.project_views = QWidget()
        shelf_layout = QVBoxLayout(self.project_views)
        shelf_layout.setContentsMargins(0,0,0,0)
        self.artwork = ProjectArtwork(self)
        self.artwork.changed.connect(self.project_artwork_loaded)
        self.project_cards = GridCards()
        self.ambient.subscribe(self.project_cards)
        self.project_cards.activated.connect(lambda index: self.zoom_into(
            self.project_cards, index, lambda: self.open_project(self.filtered_projects[index])))
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
        self.ambient.subscribe(self.choice_cards)
        self.choice_cards.card_height = 264
        self.choice_cards.fit_rows = True
        self.choice_cards.activated.connect(lambda index: self.zoom_into(
            self.choice_cards, index, lambda: self.choice_selected(index)))
        layout.addWidget(self.choice_cards,1)
        self.file_controls = QWidget()
        controls_layout = QVBoxLayout(self.file_controls)
        controls_layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.file_controls)
        row = QHBoxLayout()
        self.file_search = QLineEdit()
        self.file_search.setPlaceholderText("Search filenames, shots or paths")
        self.file_search.addAction(search_icon(), QLineEdit.LeadingPosition)
        self.file_search.textChanged.connect(self.filter_files)
        row.addWidget(self.file_search, 1)
        self.file_kind = QComboBox()
        self.file_kind.addItem("Working files", "working")
        self.file_kind.addItem("Outputs & previews", "output")
        self.file_kind.addItem("All files", "")
        self.file_kind.currentIndexChanged.connect(self.filter_files)
        self.ai_filter = QComboBox()
        self.ai_filter.addItem('All AI files', '')
        for key, title in indexer.AI_COLLECTIONS.items():
            self.ai_filter.addItem(title, key)
        self.ai_filter.currentIndexChanged.connect(self.filter_files)
        controls_layout.addWidget(self.ai_filter)
        row.addWidget(self.file_kind)
        self.filters = {}
        for key, title in (("application", "All applications"),):
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
        self.detail_info.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
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
                                         ("Reveal in Explorer", self.reveal_selected, False), ("Copy path", self.copy_selected, False),
                                         ("Favorite file", self.favorite_selected, False))):
            if index in (0,2):
                item = button(text,callback,primary)
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
        self.comments_button = button('Read / write comments', self.file_comments)
        inner.addWidget(self.comments_button)
        detail.setMinimumHeight(210)
        split.addWidget(detail)
        split.setStretchFactor(0, 1)
        layout.addWidget(split, 1)
        self.assign_button = button("Assign stage…", self.assign_stage)
        row.addWidget(self.assign_button)
        self.update_details()

    def zoom_into(self, grid, index, action):
        """Open a card with a shared-element zoom: its colour field becomes the
        next level and its artwork flies through, then the new level cascades."""
        source = grid.zoom_source(index) if enabled(self) and self.isVisible() and grid.isVisible() else None
        if source:
            # The rise starts where the card sits in the stereo field and arrives centre stage.
            self.sound.at('open', self.screen_x(grid, source['rect'].center().toPoint()))
        else:
            self.sound.play('open-center')
        host = self.pages['Projects']
        picture = snapshot(grid) if source else None
        offset = grid.mapTo(host, QPoint(0, 0))
        if source:
            # The next level's colour spreads from the card that was opened.
            self.wave_from(grid, source['rect'].center().toPoint())
        try:
            action()
        finally:
            self._wave_origin = None
        if not source or self.stack.currentWidget() is not host:
            return
        old = getattr(self, '_zoom', None)
        if old:
            old.finish()
        rect, art = source['rect'].translated(offset), source['art'].translated(offset)
        self._zoom = ZoomThrough(host, rect, art, source['colors'], source['pixmap'], source['title'], picture, offset)
        zoom = self._zoom
        zoom.destroyed.connect(lambda: setattr(self, '_zoom', None) if getattr(self, '_zoom', None) is zoom else None)
        cascade(self.work_panel, 300)

    def browse_projects(self):
        self.scene(1)
        returning = self.work_panel.isVisible()
        self.project_views.show()
        self.work_panel.hide()
        self.back_button.hide()
        if self.stack.currentWidget() is self.pages["Projects"]:
            self.page_title.setText("Projects")
        self.project_cards.setFocus()
        if returning:
            # Going back up a level: content settles down from above.
            cascade(self.project_views, 0, -26)
            self.sound.play('back')

    @staticmethod
    def variant_of(file):
        value = file.get('variant','Unspecified')
        return 'General' if value in ('Unspecified','') else value

    def browse_back(self):
        if not self.work_panel.isVisible():return
        if self.browse_step=='sections':
            self.browse_projects()
        elif self.project_section in ('assets','preview'):
            self.breadcrumb_clicked('collections' if self.browse_step=='files' else 'sections')
        elif self.browse_step=='files':
            self.breadcrumb_clicked('stages' if self.selected_area=='3d' else 'areas')
        elif self.browse_step=='stages':
            self.breadcrumb_clicked('areas')
        elif self.browse_step=='areas' and any(self.variant_of(f)!='General' for f in self.files if indexer.in_section(f,'work')):
            self.breadcrumb_clicked('versions')
        else:self.breadcrumb_clicked('sections')

    def breadcrumb_clicked(self, target):
        if target == 'projects':
            self.browse_projects()
            return
        if target == 'sections':
            self.selected_area = None
            self.selected_variant = self.selected_stage = None
            self.selected_collection = None
            self.project_section = 'work'
            self.browse_step = 'sections'
        elif target == 'collections':
            self.selected_collection = None
            self.browse_step = 'collections'
        elif target == 'versions':
            self.selected_area = None
            self.selected_variant = self.selected_stage = None
            self.browse_step = 'versions'
        elif target == 'areas':
            self.selected_area = self.selected_stage = None
            self.browse_step = 'areas'
        elif target == 'stages':
            self.selected_stage = None
            self.browse_step = 'stages'
        self.filter_files()
        self.wave_from(self.breadcrumb, QPoint(0, self.breadcrumb.height()//2))
        self.scene(self.projects_scene())
        self._wave_origin = None
        cascade(self.work_panel, 0, -26)
        self.sound.play('back')

    def update_browser(self):
        if not self.project:
            return
        import html
        workfiles = [f for f in self.files if indexer.in_section(f,'work')]
        variants = sorted({self.variant_of(f) for f in workfiles},key=indexer.natural)
        if self.browse_step != 'sections' and self.selected_variant is not None and self.selected_variant not in variants and not self.scan_pending:
            self.selected_variant = self.selected_stage = None
            self.selected_area = None
            self.browse_step = 'versions'
        named = any(v != 'General' for v in variants)
        if self.browse_step == 'versions' and not named and (self.files or not self.scan_pending):
            self.browse_step = 'areas'
        file_mode = self.browse_step == 'files'
        self.ai_filter.setVisible(file_mode and self.project_section=='work' and self.selected_area=='ai_generation')
        self.assign_button.setVisible(file_mode and self.project_section=='work' and self.selected_area in (None,'3d','other'))
        self.choice_cards.setVisible(not file_mode)
        self.file_controls.setVisible(file_mode)
        self.file_split.setVisible(file_mode)
        self.file_kind.setVisible(self.project_section not in ('assets','preview'))
        crumbs = '<a href="projects" style="color:#f3dcff">Projects</a>  ›  '
        crumbs += '<a href="sections" style="color:#f3dcff">'+html.escape(Path(self.project).name)+'</a>'
        if self.project_section in ('assets','preview'):
            crumbs += '  ›  <a href="collections" style="color:#f3dcff">'+{'assets':'Assets','preview':'Preview'}[self.project_section]+'</a>'
            if self.selected_collection:
                categories=indexer.CLIENT_CATEGORIES if self.project_section=='assets' else indexer.PREVIEW_GROUPS
                crumbs += '  ›  '+html.escape(categories[self.selected_collection])
        elif self.browse_step != 'sections':
            crumbs += '  ›  <a href="versions" style="color:#f3dcff">'+('Versions' if named else 'Working files')+'</a>'
        if self.project_section == 'work' and self.selected_variant is not None:
            crumbs += '  ›  <a href="areas" style="color:#f3dcff">'+html.escape(self.selected_variant)+'</a>'
        elif self.project_section == 'work' and self.browse_step not in ('versions','sections'):
            crumbs += '  ›  <a href="areas" style="color:#f3dcff">Work areas</a>'
        if self.selected_area:
            area_title = indexer.WORK_AREAS[self.selected_area]
            crumbs += '  ›  <a href="stages" style="color:#f3dcff">'+area_title+'</a>' if self.selected_area=='3d' else '  ›  '+area_title
        if self.selected_stage is not None:
            crumbs += '  ›  '+('All stages' if self.selected_stage == ALL_STAGES else STAGES[self.selected_stage])
        self.breadcrumb.setText(crumbs)
        if self.browse_step == 'sections':
            entries = [
                {'name':'Assets','path':'assets','application':'SECTION','artwork':self.asset('ui-icons','assets.png'),
                 'details':f"{plural(sum(indexer.in_section(f,'assets') for f in self.files), 'asset')} · Client materials and brief"},
                {'name':'Versions' if named else 'Working files','path':'work','application':'SECTION',
                 'artwork':self.asset('ui-icons','versions.png' if named else 'files.png'),
                 'details':f"{plural(len(variants), 'version')}" if named else 'Explore working files by stage'},
                {'name':'Preview','path':'preview','application':'SECTION','artwork':self.asset('ui-icons','preview.png'),
                 'details':f"{plural(sum(indexer.in_section(f,'preview') for f in self.files), 'file')} · Renders, playblasts and delivery"},
            ]
        elif self.browse_step == 'collections':
            scoped=[f for f in self.files if indexer.in_section(f,self.project_section)]
            if self.project_section=='assets':
                categories=indexer.CLIENT_CATEGORIES
                artwork={'fonts':('ui-icons','client-fonts.png'),'logos':('ui-icons','client-logos.png'),
                         'brand_guidelines':('ui-icons','client-guide.png'),'brief':('ui-icons','client-brief.png'),
                         'packaging':('project-art','product.png'),'product_photos':('project-art','photo.png'),
                         'music':('project-art','music.png'),'video_references':('ui-icons','preview.png'),
                         'other':('ui-icons','assets.png')}
                classify=indexer.asset_category
            else:
                categories=indexer.PREVIEW_GROUPS
                artwork={'full':('ui-icons','preview.png'),'shot':('project-art','film.png')}
                classify=indexer.preview_group
            entries=[{'name':title,'path':key,'application':'COLLECTION','artwork':self.asset(*artwork[key]),
                      'details':f"{plural(sum(classify(f)==key for f in scoped), 'file')} · Open →"}
                     for key,title in categories.items()]
        elif self.browse_step == 'versions':
            version_art=str(Path(__file__).resolve().parents[1]/'assets/ui-icons/versions.png')
            entries = [{'name':v,'path':v,'application':'VERSION','artwork':version_art,'subtitle':f"{sum(self.variant_of(f)==v for f in workfiles)} files · Choose version →"} for v in variants]
            self.choice_cards.empty_message = 'Discovering project versions…' if self.scan_pending else 'No working files found in this project.'
        elif self.browse_step == 'areas':
            scoped = [f for f in workfiles if self.selected_variant is None or self.variant_of(f)==self.selected_variant]
            art = {'3d':('stage-icons','modelling.png'),'graphic_design':('project-art','design.png'),
                   'motion_graphics':('project-art','motion.png'),'ai_generation':('project-art','idea.png'),
                   'other':('project-art','compass.png')}
            entries = [{'name':title,'path':key,'application':'AREA','artwork':self.asset(*art[key]),
                        'details':f"{plural(sum(indexer.work_area(f)==key for f in scoped), 'file')} · Open →"}
                       for key,title in indexer.WORK_AREAS.items() if key!='other' or any(indexer.work_area(f)=='other' for f in scoped)]
        elif self.browse_step == 'stages':
            scoped = [f for f in workfiles if f.get('kind','working')=='working'
                      and (self.selected_area is None or indexer.work_area(f)==self.selected_area)
                      and (self.selected_variant is None or self.variant_of(f)==self.selected_variant)]
            counts = {}
            for f in scoped:
                key = self.stage_store.stage(f,self.stage_document)
                counts[key] = counts.get(key,0)+1
            # ALL opens every stage at once; template stages always show, and
            # Unassigned appears only while there are loose saves to sort.
            entries = [{'name':'All stages','path':ALL_STAGES,'application':'STAGE',
                        'artwork':self.stage_artwork(ALL_STAGES) if Path(self.stage_artwork(ALL_STAGES)).is_file() else None,
                        'details':f"{plural(len(scoped), 'working file')} across every stage",
                        'subtitle':f"{plural(len(scoped), 'file')} · Open all →"}]
            for key,title in STAGES.items():
                if key == 'unassigned':
                    continue
                artwork=self.stage_artwork(key)
                entries.append({'name':title,'path':key,'application':'STAGE',
                    'artwork':artwork if Path(artwork).is_file() else None,
                    'details':f"{plural(counts.get(key,0), 'file')} · {STAGE_NOTES[key]}",
                    'subtitle':f"{plural(counts.get(key,0), 'file')} · Choose stage →"})
        else:
            entries=[]
        self.choice_cards.equal_pair = self.browse_step == 'collections' and self.project_section == 'preview'
        self.choice_cards.set_entries(entries)
        if self.stack.currentWidget() is self.pages["Projects"]:
            self.page_title.setText(self.projects_title())

    def choice_selected(self,index):
        entries=self.choice_cards.entries
        if not 0<=index<len(entries):return
        if self.browse_step == 'sections':
            self.selected_area = None
            self.project_section = entries[index]['path']
            self.selected_variant = self.selected_stage = None
            self.selected_collection = None
            self.browse_step = 'versions' if self.project_section == 'work' else 'collections'
            for combo in self.filters.values():combo.setCurrentIndex(0)
            self.file_kind.setCurrentIndex(0 if self.project_section == 'work' else 1)
        elif self.browse_step == 'collections':
            self.selected_collection=entries[index]['path']
            self.browse_step='files'
        elif self.browse_step == 'versions':
            self.selected_variant=entries[index]['path']
            self.selected_stage=None
            self.selected_area=None
            self.browse_step='areas'
        elif self.browse_step == 'areas':
            self.selected_area=entries[index]['path']
            self.selected_stage=None
            self.browse_step='stages' if self.selected_area=='3d' else 'files'
            self.file_kind.setCurrentIndex(2 if self.selected_area=='ai_generation' else 0)
            self.ai_filter.setCurrentIndex(0)
        else:
            self.selected_stage=entries[index]['path']
            self.browse_step='files'
        self.file_search.clear()
        self.filter_files()
        self.scene(self.projects_scene())
        cascade(self.work_panel, 60)

    def assign_stage(self):
        files=self.file_cards.selected_files()
        if not files or not self.stage_document.get('writable',False):return
        dialog=QDialog(self)
        dialog.setWindowTitle('Assign production stage')
        layout=QVBoxLayout(dialog)
        layout.addWidget(label(f'Assign a stage to {len(files)} selected file(s).','section'))
        combo=QComboBox()
        for key,title in STAGES.items():
            if key!='unassigned':combo.addItem(title,key)
        combo.setCurrentIndex(combo.findData(self.stage_store.stage(files[0],self.stage_document)))
        layout.addWidget(combo)
        layout.addWidget(label('Files stay in their existing folders. Labels are shared with the project team.','subtitle',True))
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        self.sound.play('dialog')
        if dialog.exec()!=QDialog.Accepted:return
        self.apply_stage(files,combo.currentData())

    def apply_stage(self,files,stage):
        store=self.stage_store;project=self.project;expected=self.stage_document.get('fingerprint')
        def saved(document):
            if self.project!=project:return
            self.stage_document=document
            self.filter_files()
            self.status.setText(f'{len(files)} files assigned to {STAGES[stage]}')
            self.sound.play('success')
            activity('Stage assigned',path=project,stage=stage,count=len(files))
        def failed(message):
            if self.project==project:
                self.stage_document={**self.stage_document,'writable':False}
                self.update_details()
            self.error(message+'\nRefresh the project before assigning again. Check write access to its _TOOLS folder.')
        self.worker(lambda job:store.save([f['path'] for f in files],stage,expected),saved,failed)

    def search_projects(self):
        before = list(getattr(self, 'filtered_projects', []))
        self.render_projects()
        self.browse_projects()
        if self.filtered_projects != before:
            self.sound.play('shuffle')

    def worker(self, fn, done, failure=None):
        job = Worker(fn)
        job.result.connect(done)
        job.failure.connect(failure or self.error)
        job.progress.connect(lambda count, directory: self.status.setText(f"{count:,} files found  ·  {Path(directory).name or directory}"))
        job.finished.connect(lambda: self.finished_job(job))
        self.jobs.append(job)
        self.orb.show()
        self.orb.set_busy(True)
        self.progress_bar.set_active(not self.settings.data["reduced_motion"])
        self.cancel_button.show()
        job.start()
        return job

    def finished_job(self, job):
        if job in self.jobs:
            self.jobs.remove(job)
        job.deleteLater()
        if not self.jobs:
            self.orb.set_busy(False)
            self.orb.show()
            self.progress_bar.set_active(False)
            self.cancel_button.hide()
            if self._refresh_cue is not None:
                # Resolve once the wave has played through, never on top of it.
                elapsed = (time.monotonic()-self._refresh_cue)*1000
                self._refresh_cue = None
                self.sound.play('done', delay=max(120, 1100-elapsed))

    def cancel_jobs(self):
        if self.jobs and not getattr(self, '_closing', False):
            self.sound.play('cancel')
        self._refresh_cue = None
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
        if not self.projects:
            self.project_cards.empty_message = ''
        self.worker(gather, self.projects_loaded)

    def projects_loaded(self, result):
        self.project_cards.empty_message = 'No matching projects. Check your search and storage roots.'
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
        self.status.setText(f"{plural(len(self.projects), 'project')} available" + (" · Some storage unavailable" if result["errors"] else ""))
        for project in self.projects:
            self.artwork.request(project, refresh=True)
        self.render_projects()
        if self.stack.currentWidget() == self.pages["Favorites"]:
            self.refresh_favorites()

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
                self.project_cards.palettes.clear()
                self.project_cards.update()
                break

    def open_project(self, path, preserve_context=False):
        if not path:
            return
        if path != self.project or not preserve_context:
            self.file_cards.clear()
            self.selected_variant = None
            self.selected_stage = None
            self.browse_step = "sections"
            self.project_section = 'work'
            self.selected_area = None
            self.selected_collection = None
        self.project = path
        self.project_views.hide()
        self.work_panel.show()
        if not self.back_button.isVisible():
            self.back_button.show()
            reveal_page(self.back_button, 120, 0)
        picker_index = self.project_picker.findData(path)
        if picker_index >= 0:
            self.project_picker.setCurrentIndex(picker_index)
        self.settings.recent(path)
        self.navigate("Projects")
        self.scene(self.projects_scene())
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
        self.status.setText(f"{plural(working, 'working file')} · {plural(outputs, 'output')}" + suffix + (f" · {len(result['errors'])} storage notices" if result["errors"] else ""))
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
        before = [f['path'] for f in self.display_files]
        typed = self.sender() in (getattr(self, 'file_search', None), getattr(self, 'file_kind', None), *getattr(self, 'filters', {}).values())
        self.file_cards.empty_message = 'No files match these filters. Try another application or clear your search.' if self.project else 'Choose a project above to discover its creative files.'
        search = self.file_search.text().lower()
        self.display_files = [f for f in self.files if indexer.in_section(f,self.project_section)
                              and (self.selected_collection is None or (indexer.asset_category(f) if self.project_section=='assets' else indexer.preview_group(f))==self.selected_collection)
                              and (self.project_section in ('assets','preview') or not self.file_kind.currentData() or f.get("kind", "working") == self.file_kind.currentData())
                              and (self.project_section!='work' or self.selected_area is None or indexer.work_area(f)==self.selected_area)
                              and (self.project_section!='work' or self.selected_area!='ai_generation' or not self.ai_filter.currentData() or indexer.ai_collection(f)==self.ai_filter.currentData())
                              and search in f["relative"].lower()
                              and all(not combo.currentData() or f[key] == combo.currentData() for key, combo in self.filters.items())]
        everything = self.selected_stage == ALL_STAGES
        self.display_files = [f for f in self.display_files
                              if (self.selected_variant is None or self.variant_of(f)==self.selected_variant)
                              and (self.selected_stage is None or everything
                                   or self.stage_store.stage(f,self.stage_document)==self.selected_stage)]
        if everything:
            # All stages at once: each row also names its stage folder (one level
            # up), and the newest save comes first, since versions run across stages.
            def newest(f):
                digits=''.join(ch for ch in f.get('version','') if ch.isdigit())
                return (indexer.natural(f.get('shot','')), -int(digits or 0), indexer.natural(f['name']))
            self.display_files = [{**f,'folder':stage_folder(f),'stage_title':STAGES[self.stage_store.stage(f,self.stage_document)]}
                                  for f in sorted(self.display_files,key=newest)]
        self.file_cards.set_entries(self.display_files)
        self.update_browser()
        self.update_details()
        if typed and [f['path'] for f in self.display_files] != before:
            self.sound.play('shuffle')

    def selected(self):
        row = self.file_cards.currentRow()
        return self.display_files[row] if 0 <= row < len(self.display_files) else None

    def update_details(self):
        if hasattr(self, "details_panel") and self.details_panel.isVisible():
            reveal_page(self.details_panel, rise=8, start=.45)
        file = self.selected()
        self.comments_button.setEnabled(bool(file))
        self.more_actions.setEnabled(bool(file))
        if hasattr(self,"assign_button"):
            self.assign_button.setEnabled(bool(self.file_cards.selectedItems()) and self.stage_document.get("writable",False))
        for item in self.file_actions:
            item.setEnabled(bool(file))
        if not file:
            self.detail_name.setText("Select a working file")
            self.detail_info.setPlainText("Its details and actions will appear here.")
            self.preview_source=icon('Files',256).pixmap(256,256)
            self.fit_preview()
            return
        self.detail_name.setText(file["name"])
        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(self.detail_name.font())
        self.detail_name.setText(metrics.elidedText(file["name"], Qt.ElideMiddle, max(180, self.detail_name.width())))
        self.detail_name.setToolTip(file["name"])
        # Folders read as a breadcrumb rather than a wrapped wall of path text.
        folders = Path(file.get('relative', file['path'])).parent.parts
        location = '  ›  '.join(folders[-4:]) if folders else Path(file['path']).parent.name
        size = file['size']
        weight = f"{size/1048576:.1f} MB" if size >= 1048576 else f"{max(1, round(size/1024))} KB"
        context = (indexer.AI_COLLECTIONS.get(indexer.ai_collection(file),'Other AI files')
                   if self.selected_area=='ai_generation' else STAGES[self.stage_store.stage(file,self.stage_document)])
        self.detail_info.setPlainText(file["application"] + " · " + file["version"] + "\n" + file["department"] + " · " + context
                                 + "\n" + weight + "\n\n" + location)
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
        self.file_actions[2].setEnabled(True)

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
        self.sound.play('launch')
        self.status.setText("Opened " + Path(path).name)

    def file_comments(self, filepath=None, application='Neotrix Prism'):
        if not isinstance(filepath, str):
            selected = self.selected()
            if not selected:
                return
            filepath = selected['path']
        from .comment_dialog import CommentDialog
        dialog = CommentDialog(filepath, self, application)
        self.sound.play('dialog')
        dialog.exec()

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
            self.sound.play('copy')

    def favorite_selected(self):
        file = self.selected()
        if file:
            self.settings.favorite(file["path"])
            self.sound.play('favorite-add' if file["path"] in self.settings.data["favorites"] else 'favorite-remove')
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

    APP_ART = {'Blender': 'blender', 'Photoshop': 'photoshop', 'Illustrator': 'illustrator',
               'After Effects': 'after-effects', 'Fusion': 'fusion'}

    def asset(self, *parts):
        return str(Path(__file__).resolve().parents[1].joinpath('assets', *parts))

    def file_artwork(self, path, application=None):
        application = application or indexer.EXTENSIONS.get(Path(path).suffix.lower(), '')
        if application in self.APP_ART:
            return self.asset('app-icons', self.APP_ART[application]+'.png')
        return self.asset('ui-icons', 'files.png')

    def build_favorites(self):
        layout = self.page("Favorites")
        self.favorite_cards = GridCards()
        self.favorite_cards.setAccessibleName('Favorite projects and files')
        self.favorite_cards.empty_message = 'No favorites yet. Star a project or file and it stays one click away.'
        self.favorite_cards.empty_art = QPixmap(self.asset('ui-icons', 'favorites.png'))
        self.favorite_cards.activated.connect(self.open_favorite)
        self.favorite_cards.context_requested.connect(self.favorite_menu)
        self.ambient.subscribe(self.favorite_cards)
        layout.addWidget(self.favorite_cards, 1)
        actions = QHBoxLayout()
        actions.addWidget(button("Favorite current project", self.favorite_project))
        actions.addWidget(button("Remove selected favorite", self.remove_favorite))
        actions.addWidget(button("Restore favorites…", self.restore_favorites))
        actions.addStretch()
        layout.addLayout(actions)

    def refresh_favorites(self):
        self.settings.reload()
        entries = []
        for path in self.settings.data["favorites"]:
            application = indexer.EXTENSIONS.get(Path(path).suffix.lower(), '')
            is_file = bool(application) or Path(path).suffix.lower() in indexer.MEDIA
            entries.append({'name': Path(path).name, 'path': path,
                            'artwork': self.file_artwork(path, application) if is_file else self.artwork.request(path),
                            'subtitle': (application or 'Media')+' file · Open →' if is_file else 'Project · Explore project →'})
        self.favorite_cards.set_entries(entries)
        if self.settings.recovery_notice:
            self.status.setText(self.settings.recovery_notice)

    def restore_favorites(self):
        backups=self.settings.favorite_backups()
        if not backups:
            self.status.setText('No favorites backups yet. Automatic backups start with this version.')
            return
        choices=[time.strftime('%d %b %Y · %H:%M:%S',time.localtime(path.stat().st_mtime))+
                 f' · {len(items)} favorite(s) · {i+1}' for i,(path,items) in enumerate(backups)]
        selected,ok=QInputDialog.getItem(self,'Restore favorites','Choose a backup to merge with your current favorites:',choices,0,False)
        if ok:
            try:
                self.settings.restore_favorites(backups[choices.index(selected)][0])
                self.refresh_favorites()
                self.status.setText('Favorites restored. Existing favorites were kept.')
                self.sound.play('success')
            except Exception as exc:self.error(str(exc))

    def favorite_project(self):
        if self.project:
            if self.project not in self.settings.data["favorites"]:
                self.settings.favorite(self.project)
                self.sound.play('favorite-add')
            self.refresh_favorites()
        else:
            self.status.setText("Select a project first.")

    def remove_favorite(self, index=None):
        index = self.favorite_cards.selected_index if index is None or index is False else index
        if 0 <= index < len(self.favorite_cards.entries):
            self.settings.favorite(self.favorite_cards.entries[index]['path'])
            self.sound.play('favorite-remove')
            self.refresh_favorites()

    def favorite_menu(self, index, position):
        menu = QMenu(self)
        round_surface(menu)
        path = self.favorite_cards.entries[index]['path']
        menu.addAction('Open', lambda: self.open_favorite(index))
        menu.addAction('Reveal in Explorer', lambda: apps.reveal(path))
        menu.addSeparator()
        menu.addAction('Remove from favorites', lambda: self.remove_favorite(index))
        self.sound.play('menu')
        menu.exec(position)

    def open_favorite(self, index):
        if not 0 <= index < len(self.favorite_cards.entries):
            return
        path = self.favorite_cards.entries[index]['path']
        if Path(path).suffix.lower() in {**indexer.EXTENSIONS, **indexer.MEDIA}:
            try:
                self.open_path(path)
            except Exception as exc:
                self.error(str(exc))
        else:
            self.open_project(path)

    def build_activity(self):
        layout = self.page("Activity")
        self.activity_list = ActivityList()
        self.activity_list.empty_art = QPixmap(self.asset('ui-icons', 'activity.png'))
        self.activity_list.activated.connect(self.open_activity)
        self.ambient.subscribe(self.activity_list.viewport(), 2)
        layout.addWidget(self.activity_list, 1)

    def refresh_history(self):
        self.records = history()
        entries = []
        for i, record in enumerate(self.records):
            target = record.get("path", record.get("name", ""))
            application = record.get('application') or indexer.EXTENSIONS.get(Path(target).suffix.lower(), '')
            if record.get('stage'):
                artwork = self.asset('stage-icons', record['stage']+'.png')
            elif application in self.APP_ART:
                artwork = self.file_artwork(target, application)
            elif 'version' in record['event'].lower():
                artwork = self.asset('ui-icons', 'versions.png')
            else:
                artwork = self.asset('ui-icons', 'activity.png')
            detail = Path(target).name or target
            if record.get('count'):
                detail = f"{record['count']} files · {detail}"
            entries.append({'path': f"{record['time']}-{i}", 'name': record['event'], 'detail': detail,
                            'tooltip': target, 'target': target, 'artwork': artwork,
                            'when': time.strftime("%d %b · %H:%M", time.localtime(record["time"]))})
        self.activity_list.set_entries(entries)

    def open_activity(self, row):
        if not 0 <= row < self.activity_list.count():
            return
        target = self.activity_list.item(row).data(Qt.UserRole).get('target', '')
        if Path(target).is_file():
            try:
                self.open_path(target)
            except Exception as exc:
                self.error(str(exc))
        elif Path(target).is_dir():
            self.open_project(target)

    def build_settings(self):
        layout = self.page("Settings")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.settings_wheel = SmoothWheel(scroll)
        content = QWidget()
        form_layout = QVBoxLayout(content)
        frame, inner = card()
        inner.addWidget(label("Storage", "section"))
        self.roots_edit = QPlainTextEdit("\n".join(self.settings.data["roots"]))
        self.roots_edit.setPlaceholderText('Project roots, one per line')
        self.roots_edit.setToolTip('One project-library root per line. Existing project folders stay in place.')
        self.roots_edit.setMaximumHeight(85)
        inner.addWidget(self.roots_edit)
        inner.addWidget(button("Add storage folder", self.add_root))
        form_layout.addWidget(frame)
        frame, inner = card()
        inner.addWidget(label("Creative applications", "section"))
        frame.setToolTip('Empty executable paths use Windows file associations.')
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
        self.reduced = QCheckBox("Reduce motion")
        self.reduced.setChecked(self.settings.data["reduced_motion"])
        self.reduced.toggled.connect(lambda on: self.sound.play('toggle-on' if on else 'toggle-off'))
        row.addWidget(self.reduced)
        row.addStretch()
        inner.addLayout(row)
        # Sound applies immediately, so every change can be heard as it is made.
        row = QHBoxLayout()
        self.sound_box = QCheckBox("Sound effects")
        self.sound_box.setChecked(self.settings.data["sound"])
        self.sound_box.setToolTip("Soft interface sounds timed to each animation")
        self.hover_box = QCheckBox("Hover sounds")
        self.hover_box.setChecked(self.settings.data["sound_hover"])
        self.hover_box.setToolTip("A quiet note as the pointer meets cards, rows and buttons")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.settings.data["sound_volume"])
        self.volume_slider.setFixedWidth(200)
        self.volume_slider.setAccessibleName("Sound volume")
        row.addWidget(self.sound_box)
        row.addSpacing(16)
        row.addWidget(self.hover_box)
        row.addSpacing(16)
        row.addWidget(label("Volume", "subtitle"))
        row.addSpacing(6)
        row.addWidget(self.volume_slider)
        row.addStretch()
        inner.addLayout(row)
        self.volume_preview = QTimer(self)
        self.volume_preview.setSingleShot(True)
        self.volume_preview.timeout.connect(self.sound_changed)
        self.sound_box.toggled.connect(self.sound_changed)
        self.hover_box.toggled.connect(self.sound_changed)
        self.volume_slider.valueChanged.connect(lambda value: self.volume_preview.start(160))
        self.hover_box.setEnabled(self.sound_box.isChecked())
        self.volume_slider.setEnabled(self.sound_box.isChecked())
        form_layout.addWidget(frame)
        frame, inner = card()
        inner.addWidget(label('Prism', 'section'))
        pipeline = MotionButton('Prism tools')
        pipeline.setToolTip('Open Prism production tools')
        pipeline.setAccessibleName('Prism tools')
        pipeline.setIcon(icon('Settings', 22))
        menu = QMenu(pipeline)
        for title, action in (("Save New Version", self.save_current_version),
                              ("Prism managed-project browser", self.native_browser),
                              ("State Manager", self.state_manager),
                              ("Prism project settings", self.native_settings)):
            entry = menu.addAction(title)
            entry.triggered.connect(action)
        pipeline.setMenu(menu)
        inner.addWidget(pipeline, 0, Qt.AlignLeft)
        form_layout.addWidget(frame)
        form_layout.addWidget(button("Save settings", self.save_settings, True))
        from .update_panel import UpdatePanel
        self.updates = UpdatePanel(self,form_layout)
        form_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        # Discovery is per-user only; never written into the repository.
        if not self.settings.data["apps"]:
            self.settings.data["apps"] = detected
            self.settings.save()

    def sound_changed(self, *args):
        """Apply sound settings now and let the change be heard."""
        source = self.sender()
        on = self.sound_box.isChecked()
        if source is self.sound_box and not on:
            self.sound.play('toggle-off')
        self.settings.data.update(sound=on, sound_hover=self.hover_box.isChecked(),
                                  sound_volume=self.volume_slider.value())
        self.settings.save()
        self.hover_box.setEnabled(on)
        self.volume_slider.setEnabled(on)
        if source is self.sound_box and on:
            self.sound.play('toggle-on')
        elif source is self.hover_box:
            self.sound.play('toggle-on' if self.hover_box.isChecked() else 'toggle-off')
        elif source is self.volume_preview:
            self.sound.play('select')

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
                                  theme='dark', reduced_motion=self.reduced.isChecked())
        self.settings.save()
        self.apply_theme()
        self.load_projects()
        self.status.setText("Settings saved")
        self.sound.play('success')

    def refresh(self):
        self._refresh_cue = time.monotonic()
        self.sound.play('refresh')
        if self.stack.currentWidget() == self.pages["Favorites"]:
            self.refresh_favorites()
        elif self.stack.currentWidget() == self.pages["Activity"]:
            self.refresh_history()
        if enabled(self):
            # A shockwave radiates from the orb; every piece of artwork jumps
            # at the moment the wave front reaches it, sidebar included.
            page = self.stack.currentWidget()
            centre = self.orb.mapTo(self.surface, self.orb.rect().center())
            if getattr(self, 'shockwave', None) is None:
                self.shockwave = Shockwave(self.surface)
            self.shockwave.fire(QPointF(centre), page, self.surface.scene_colors()[1].lighter(430))
            def reach(widget):
                return self.shockwave.delay_for(widget.mapTo(self.surface, widget.rect().center()))
            self.surface.refresh_wave()
            self.orb.hop()
            for surface in page.findChildren(GridCards)+page.findChildren(FileList):
                if surface.isVisible():
                    surface.refresh_wave(origin=QPointF(surface.mapFrom(self.surface, centre)), speed=Shockwave.SPEED)
            for art in page.findChildren(MotionIcon)+self.sidebar.findChildren(MotionIcon):
                if art.isVisible():
                    art.refresh_wave(reach(art))
            for tile in page.findChildren(GradientTile):
                if tile.isVisible():
                    tile.refresh_wave(reach(tile))
            for item in self.nav.values():
                item.refresh_wave(reach(item))
            # Every other panel rides the wave too: pushed away from the orb as
            # the front passes, then one rebound (translation only).
            blocks = [block for block in motion_blocks(page) if not isinstance(block, (GridCards, FileList, QAbstractScrollArea))]
            ripple_blocks(self.surface, blocks+[self.page_title], QPointF(centre), Shockwave.SPEED)
            self.shockwave.raise_()  # the light passes over the riding panels
            self.sound.wave(self.wave_arrivals(page))
        if self.project and self.stack.currentWidget() == self.pages["Projects"] and self.work_panel.isVisible():
            self.open_project(self.project, preserve_context=True)
        else:
            self.load_projects()

    def wave_arrivals(self, page):
        """When the wave reaches each piece of artwork: cards are placed by their
        x position (the grid plays like a keyboard); list rows climb the scale."""
        arrivals = []
        for grid in page.findChildren(GridCards):
            if grid.isVisible():
                for index, rect in grid.card_rects().items():
                    lag = grid.refresh_lags.get(grid.entries[index].get('path'))
                    if lag is not None:
                        arrivals.append((lag, self.screen_x(grid, rect.center().toPoint()), None))
        rows = sorted(lag for rows in page.findChildren(FileList) if rows.isVisible() for lag in rows.refresh_lags.values())
        arrivals += [(lag, 0.0, n) for n, lag in enumerate(rows[:7])]
        return arrivals

    def error(self, message):
        self.sound.play('alert')
        self.status.setText(message[:150])
        QMessageBox.warning(self, "Neotrix Prism", message)

    def closeEvent(self, event):
        if hasattr(self,'updates') and not self.jobs and not self.updates.can_close():
            event.ignore()
            if self.updates.task and self.updates.task.isRunning():
                QTimer.singleShot(150,self,self.close)
            return
        if self.jobs:
            self._closing = True
            self.cancel_jobs()
            event.ignore()
            QTimer.singleShot(150, self.close)
        else:
            self.sound.shutdown()
            event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, 'introduced', False):
            # Before the first paint, so the finished layout never flashes.
            self.introduced = True
            self.play_intro()
        else:
            QTimer.singleShot(0, self, lambda: self.move_selection(next((n for n, b in self.nav.items() if b.isChecked()), "Projects")))

    def play_intro(self):
        """Opening sequence: light rises, the chrome drops in, the title types
        on, content cascades and the orb lands last as the call to action."""
        current = next((n for n, b in self.nav.items() if b.isChecked()), "Projects")
        self.sound.prepare()
        if not enabled(self):
            QTimer.singleShot(0, self, lambda: self.move_selection(current))
            return
        self.sound.play('intro')
        self.surface.play_intro()
        for art in self.sidebar.findChildren(MotionIcon):
            art.appear(60)
        for i, item in enumerate(self.nav.values()):
            item.intro(150+i*70)
        column = self.nav[current].geometry()
        middle = column.center().y()
        # The selection pill starts as a sliver and blooms open once its icon lands.
        self.rail_edges = [float(middle-4), float(middle+4)]
        self.selection_rail.setGeometry(column.x(), middle-4, column.width(), 8)
        QTimer.singleShot(420, self, lambda: self.move_selection(current))
        self.page_title.play()
        cascade(self.stack.currentWidget(), 240)
        for lag, widget in ((380, self.status), (440, self.progress_bar), (470, self.cancel_button)):
            reveal_page(widget, lag, 12)
        self.orb.intro(560)

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
            self.progress_bar.pause(self.isMinimized())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "selection_rail"):
            def align():
                current = next((n for n, b in self.nav.items() if b.isChecked()), "Projects")
                if not physics.get(self, ('rail', 'top')) and not physics.get(self, ('rail', 'bottom')):
                    target = self.nav[current].geometry()
                    self.selection_rail.setGeometry(target)
                    self.rail_edges = [float(target.top()), float(target.bottom()+1)]
                if hasattr(self,'preview_image'):
                    self.preview_image.setFixedHeight(44 if self.height()<=760 else 78)
                    self.fit_preview()
            QTimer.singleShot(0, self, align)
