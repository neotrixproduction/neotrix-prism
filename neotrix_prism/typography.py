"""Display/text roles, packaged OFL fonts and optional locally licensed typefaces."""
import os
from pathlib import Path
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication

_loaded = False


def initialize():
    global _loaded
    app = QApplication.instance()
    if not app:
        return
    if not _loaded:
        directories = [Path(__file__).resolve().parents[1] / 'assets/fonts']
        if os.environ.get('NEOTRIX_FONT_DIR'):
            directories.append(Path(os.environ['NEOTRIX_FONT_DIR']))
        for directory in directories:
            for pattern in ('*.ttf', '*.otf'):
                for file in directory.glob(pattern):
                    QFontDatabase.addApplicationFont(str(file))
        _loaded = True
    display, text = roles()
    font = QFont(text)
    font.setPixelSize(13)
    app.setFont(font)


def roles():
    available = set(QFontDatabase.families()) if QApplication.instance() else set()
    def resolve(variable, fallback):
        requested = os.environ.get(variable, fallback)
        return requested if requested in available else fallback if fallback in available else 'Segoe UI'
    return resolve('NEOTRIX_FONT_DISPLAY', 'Manrope'), resolve('NEOTRIX_FONT_TEXT', 'Manrope')
