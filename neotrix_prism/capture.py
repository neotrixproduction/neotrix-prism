"""Capture real Qt widgets for visual QA; no rendered HTML substitutes."""
from pathlib import Path
from PySide6.QtCore import QTimer
from .storage import atomic_json


def capture(window, directory, application):
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    pages = ["Home", "Projects", "Favorites", "Workflows", "Activity", "Settings"]
    if window.projects:
        recent = window.settings.data["recent"]
        project = next((p for p in recent if p in window.projects), window.projects[0])
        window.open_project(project)
    index = [0]
    def finish():
        window.grab().save(str(output/'project-library.png'))
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
