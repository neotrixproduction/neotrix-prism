"""Capture real Qt widgets for visual QA; no rendered HTML substitutes."""
from pathlib import Path
from PySide6.QtCore import QTimer
from .storage import atomic_json


def capture(window, directory, application):
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    pages = ["Home", "Projects", "Favorites", "Activity", "Settings"]
    project = None
    if window.projects:
        recent = window.settings.data["recent"]
        project = next((p for p in recent if p in window.projects), window.projects[0])
        window.open_project(project)
    index = [0]
    def finish():
        window.grab().save(str(output/'project-library.png'))
        if not project:
            files()
            return
        window.open_project(project)
        QTimer.singleShot(300, choices)

    def choices():
        if window.jobs:
            QTimer.singleShot(300,choices);return
        window.grab().save(str(output/'versions.png'))
        if window.browse_step=='versions' and window.choice_cards.entries:
            window.choice_selected(next((i for i,e in enumerate(window.choice_cards.entries) if e['path']!='General'),0))
        window.grab().save(str(output/'stages.png'))
        key=next((key for key in ('lighting','unassigned','other') if any(window.stage_store.stage(f,window.stage_document)==key for f in window.files)), 'other')
        window.selected_stage=key;window.browse_step='files';window.filter_files()
        if window.file_cards.rowCount():window.file_cards.selectRow(0)
        QTimer.singleShot(150,files)

    def files():
        window.grab().save(str(output/'projects.png'))
        atomic_json(output / "capture.json", {"pages": pages, "project_library":True,"size": [window.width(), window.height()],
                                              "scale": window.devicePixelRatioF(), "theme": window.settings.data["theme"],
                                              "files": len(window.files), "projects": len(window.projects)})
        window.close()
        application.quit()
    def next_page():
        if window.jobs:
            QTimer.singleShot(300, next_page)
            return
        if index[0] == len(pages):
            window.navigate('Projects')
            window.browse_projects()
            QTimer.singleShot(220,finish)
            return
        page = pages[index[0]]
        window.navigate(page)
        if page == "Projects" and window.file_cards.rowCount():
            window.file_cards.selectRow(0)
        def grab():
            window.grab().save(str(output / (page.lower() + ".png")))
            index[0] += 1
            QTimer.singleShot(60, next_page)
        QTimer.singleShot(220, grab)
    next_page()
