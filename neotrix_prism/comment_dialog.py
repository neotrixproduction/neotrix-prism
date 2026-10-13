"""Shared read/write discussion window for every creative file type."""
import getpass
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QLineEdit, QHBoxLayout, QPushButton
from .comments import load_comments, add_comment


class CommentDialog(QDialog):
    def __init__(self, filepath, parent=None, application='Neotrix Prism'):
        super().__init__(parent)
        self.filepath, self.application = filepath, application
        self.setWindowTitle('File comments · ' + Path(filepath).name)
        self.resize(640, 540)
        layout = QVBoxLayout(self)
        title = QLabel(Path(filepath).name)
        title.setToolTip(filepath)
        layout.addWidget(title)
        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setAccessibleName('Shared file discussion')
        layout.addWidget(self.history, 1)
        self.author = QLineEdit(getpass.getuser())
        self.author.setPlaceholderText('Your name')
        self.author.setMaxLength(120)
        layout.addWidget(self.author)
        self.message = QPlainTextEdit()
        self.message.setPlaceholderText('Write a comment…')
        self.message.setMaximumHeight(110)
        layout.addWidget(self.message)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        for label, callback in [('Refresh comments', self.refresh), ('Add comment', self.append), ('Close', self.close)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        try:
            records, errors = load_comments(self.filepath)
            self.history.setPlainText('\n\n'.join(f"{c['author']} · {c['created']} · {c.get('application', 'Blender / legacy')}\n{c['text']}" for c in records) or 'No comments yet. Start the discussion.')
            self.status.setText('\n'.join(errors) if errors else f'{len(records)} shared comments')
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))

    def append(self):
        try:
            add_comment(self.filepath, self.author.text(), self.message.toPlainText(), self.application)
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))
            return
        self.message.clear()
        self.refresh()
