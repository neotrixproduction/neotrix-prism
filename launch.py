"""Portable Neotrix Prism entry point."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Prism" / "Scripts"))
os.environ.setdefault("PRISM_NO_LIBS", "1")
os.environ.setdefault("PRISM_USER_PREFS", str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NeotrixPrism" / "Prism"))
os.environ.setdefault("PRISM_IGNORE_AUTOLOAD_PLUGINS", "Hub,PrismInternals")
os.environ.setdefault("PRISM_ROOT", str(ROOT / "Prism"))
os.environ.setdefault("QT_API", "pyside6")
DLL_HANDLES = []
if os.name == "nt":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Neotrix.Prism")
    for folder in (ROOT / "runtime" / "Lib" / "win32", ROOT / "runtime" / "Lib" / "win32" / "lib",
                   ROOT / "runtime" / "Lib" / "pywin32_system32"):
        if folder.exists():
            sys.path.insert(0, str(folder))
            if folder.name == "pywin32_system32":
                os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
                DLL_HANDLES.append(os.add_dll_directory(str(folder)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", default="Standalone", choices=["Standalone", "Photoshop", "AfterEffects"])
    parser.add_argument("--command", default="Explorer")
    parser.add_argument("--expected-source")
    parser.add_argument("--root")
    parser.add_argument("--capture-dir")
    args = parser.parse_args()
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from neotrix_prism.ui import MainWindow
    from neotrix_prism.storage import Settings
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Neotrix Prism")
    application.setOrganizationName("Neotrix")
    settings = Settings()
    if args.root:
        settings.data["roots"] = [args.root]
    core = None
    if args.app != "Standalone":
        from neotrix_prism.integration import get_core
        core = get_core(args.app)
    window = MainWindow(settings, core)
    if core:
        core._neotrix_window = window
    if args.app == "Standalone" and not args.capture_dir:
        from neotrix_prism.bridge import Bridge
        try:
            window.bridge = Bridge(window)
            application.aboutToQuit.connect(window.bridge.close)
        except OSError:
            window.status.setText("Adobe panel bridge is already running in another Neotrix Prism instance.")
    window.show()
    if args.command == "SaveVersion":
        from neotrix_prism.integration import save_version_dialog
        QTimer.singleShot(250, lambda: save_version_dialog(core, window, args.expected_source))
    elif args.command == "StateManager":
        QTimer.singleShot(250, window.state_manager)
    if args.capture_dir:
        from neotrix_prism.capture import capture
        QTimer.singleShot(2500, lambda: capture(window, args.capture_dir, application))
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
