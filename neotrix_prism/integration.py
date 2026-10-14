"""Neotrix wrappers around upstream application adapters."""
import os
import subprocess
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from .storage import Settings, user_dir
from .design import stylesheet, native_theme
from .versions import next_version, save_next

ROOT = Path(__file__).resolve().parents[1]
CORES = {}
DLL_HANDLES = []


def configure():
    os.environ["NEOTRIX_PRISM"] = "1"
    os.environ["PRISM_NO_LIBS"] = "1"
    os.environ["PRISM_ROOT"] = str(ROOT / "Prism")
    os.environ["PRISM_USER_PREFS"] = str(user_dir() / "Prism")
    os.environ["PRISM_IGNORE_AUTOLOAD_PLUGINS"] = "Hub,PrismInternals"
    os.environ["QT_API"] = "pyside6"
    os.environ["NEOTRIX_AE_PORT"] = "19888"
    for path in (ROOT, ROOT / "Prism" / "Scripts", ROOT / "runtime" / "Lib",
                 ROOT / "runtime" / "Lib" / "win32", ROOT / "runtime" / "Lib" / "win32" / "lib",
                 ROOT / "runtime" / "Lib" / "pywin32_system32"):
        if path.exists() and str(path) not in sys.path:
            sys.path.append(str(path))
    dll = ROOT / "runtime" / "Lib" / "pywin32_system32"
    if dll.exists() and hasattr(os, "add_dll_directory"):
        DLL_HANDLES.append(os.add_dll_directory(str(dll)))


def get_core(app, no_ui=False):
    loaded = sys.modules.get("PrismCore")
    if loaded and getattr(loaded, "__file__", None) and Path(loaded.__file__).resolve().parent != (ROOT / "Prism/Scripts").resolve():
        raise RuntimeError("Standard Prism is already loaded in this application session. Use the Neotrix desktop explorer, or restart the host with only Neotrix Prism enabled for its in-app tools.")
    configure()
    if app in CORES:
        return CORES[app]
    import PrismCore
    args = ["noProjectBrowser", "noSplash", "loadProject"] + (["noUI"] if no_ui else [])
    core = PrismCore.PrismCore(app=app, prismArgs=args)
    if not hasattr(core, "appPlugin"):
        raise RuntimeError("Prism could not initialize its " + app + " adapter. Check the local Prism log.")
    CORES[app] = core
    install_shell(core)
    return core


def install_shell(core):
    if getattr(core, "_neotrix_shell", False):
        return
    core._neotrix_shell = True
    native_save = core.saveScene
    core._neotrix_native_save = native_save
    core._neotrix_native_browser = core.projectBrowser
    def browser(openUi=True, **kwargs):
        from .ui import MainWindow
        if not getattr(core, "_neotrix_window", None):
            core._neotrix_window = MainWindow(core=core)
        if openUi:
            core._neotrix_window.show()
            core._neotrix_window.raise_()
        return core._neotrix_window
    def save(*args, **kwargs):
        current = core.appPlugin.getCurrentFileName(core)
        if current and core.fileInPipeline(current):
            return native_save(*args, **kwargs)
        return save_version_dialog(core, getattr(core, "_neotrix_window", None))
    core.neotrixBrowser = browser
    core.saveScene = save
    core.getPythonPath = lambda *args, **kwargs: str(ROOT / "runtime/pythonw.exe") if (ROOT / "runtime/pythonw.exe").exists() else sys.executable
    def style_native(*args, **kwargs):
        for widget in args:
            if hasattr(widget, "setStyleSheet"):
                native_theme(widget, Settings().data["theme"] == "dark")
                if hasattr(widget, "setWindowTitle"):
                    widget.setWindowTitle("Neotrix Prism · " + widget.windowTitle().replace("Prism", "").strip())
    for event in ("onProjectBrowserShow", "onStateManagerOpen", "onUserSettingsOpen"):
        core.registerCallback(event, style_native)
    qapp = QApplication.instance()
    if qapp:
        qapp.setStyleSheet(stylesheet(Settings().data["theme"] == "dark"))
    # Upstream keeps callbacks and adapter state intact; only UI entry points differ.


def save_version_dialog(core, parent=None, expected_source=None):
    if core is None:
        raise RuntimeError("An application connection is required to save the active document.")
    current = core.appPlugin.getCurrentFileName(core)
    original_document_path = current
    if expected_source and (not current or os.path.normcase(os.path.abspath(current)) != os.path.normcase(os.path.abspath(expected_source))):
        QMessageBox.warning(parent, "Active document differs",
                            "The selected file is not the active document in the application. Open it there before saving a new version.")
        return None
    if not current:
        extension = {"Blender": ".blend", "Photoshop": ".psd", "AfterEffects": ".aep"}.get(core.requestedApp, "")
        current, _ = QFileDialog.getSaveFileName(parent, "Choose the first working-file name", "Untitled" + extension,
                                                "Working file (*" + extension + ")")
        if not current:
            return None
        if not Path(current).suffix:
            current += extension
    try:
        destination = next_version(current)
        result = QMessageBox.question(parent, "Save new working version",
                                      "Save the current document, including unsaved edits, as:\n\n" + str(destination),
                                      QMessageBox.Save | QMessageBox.Cancel, QMessageBox.Save)
        if result != QMessageBox.Save:
            return None
        def adapter(path):
            active = core.appPlugin.getCurrentFileName(core)
            active_key = os.path.normcase(os.path.abspath(active)) if active else ""
            original_key = os.path.normcase(os.path.abspath(original_document_path)) if original_document_path else ""
            if active_key != original_key:
                raise RuntimeError("The active document changed while the save preview was open. Review the current document and try again.")
            # Photoshop's upstream successful save returns None; the saved file and
            # current document path are the reliable success checks.
            value = core.appPlugin.saveScene(core, path.replace("\\", "/"))
            if value is False or value == "":
                return False
            actual = core.appPlugin.getCurrentFileName(core)
            return bool(actual and os.path.normcase(os.path.abspath(actual)) == os.path.normcase(os.path.abspath(path)))
        from .project_metadata import inheritance_snapshot
        inheritance = inheritance_snapshot(current, getattr(parent,'project',None))
        saved = save_next(current, adapter, expected=destination)
        if inheritance:
            store, expected, stage = inheritance
            try:
                store.save([saved],stage,expected)
            except Exception as exc:
                QMessageBox.warning(parent, 'Stage label', 'The document was saved successfully, but its stage label could not be inherited.\n'+str(exc))
        if parent and getattr(parent, "project", None):
            parent.refresh()
        return saved
    except Exception as exc:
        QMessageBox.warning(parent, "Version save", str(exc))
        return None


def launch_integration(app, command="Explorer", expected_source=None):
    app = app.replace(" ", "")
    if app == "Blender":
        raise RuntimeError("Open the file in Blender and use the Neotrix panel's Save New Version button.")
    python = ROOT / "runtime" / "pythonw.exe"
    if not python.exists():
        python = Path(sys.executable)
    args = [str(python), str(ROOT / "launch.py"), "--app", app, "--command", command]
    if expected_source:
        args += ["--expected-source", expected_source]
    return subprocess.Popen(args, shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
