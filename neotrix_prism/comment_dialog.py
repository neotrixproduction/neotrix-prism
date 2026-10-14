"""Shared comments in the same rounded, living glass shell as the explorer."""
import getpass
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QEvent
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QLabel, QPlainTextEdit,
                              QLineEdit, QHBoxLayout, QScrollArea)
from .comments import load_comments, add_comment
from .design import stylesheet, palette
from .motion import MotionButton, MotionIcon, cascade, SmoothWheel
from .surfaces import Atmosphere
from .ambient import Ambient
from .window_chrome import RoundedShell
from .cards import round_surface
from .storage import Settings


class CommentTask(QThread):
    result = Signal(object)
    failure = Signal(str)

    def __init__(self, fn, parent):
        super().__init__(parent)
        self.fn=fn

    def run(self):
        try:self.result.emit(self.fn())
        except Exception as exc:self.failure.emit(str(exc))


class CommentDialog(QDialog):
    def __init__(self, filepath, parent=None, application='Neotrix Prism'):
        super().__init__(parent)
        from .ui import card, label
        self.filepath, self.application=filepath,application
        self.settings=getattr(parent,'settings',None) or Settings()
        self.sound=getattr(parent,'sound',None)
        self.task=None
        self.setObjectName('commentDialog')
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('Comments · '+Path(filepath).name)
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1]/'assets/neotrix.ico')))
        self.setStyleSheet(stylesheet(True)+'\nQDialog#commentDialog {background:transparent;}')
        self.setPalette(palette(True))
        self.resize(760,680);self.setMinimumSize(620,540)
        outer=QVBoxLayout(self);outer.setContentsMargins(8,8,8,8)
        shell=RoundedShell();outer.addWidget(shell)
        shell_layout=QVBoxLayout(shell);shell_layout.setContentsMargins(0,0,0,0)
        self.surface=Atmosphere();shell_layout.addWidget(self.surface)
        if parent and hasattr(parent,'surface'):
            self.surface.current=parent.surface.scene_colors()
        self.ambient=Ambient(self);self.ambient.subscribe(self.surface,3)
        layout=QVBoxLayout(self.surface);layout.setContentsMargins(24,18,24,24);layout.setSpacing(16)
        self.caption=QWidget();self.caption.installEventFilter(self)
        head=QHBoxLayout(self.caption);head.setContentsMargins(0,0,0,0)
        title=label('Comments','section');title.setAttribute(Qt.WA_TransparentForMouseEvents)
        head.addWidget(title);head.addStretch()
        close=MotionButton('×');close.setFixedSize(32,32);close.setAccessibleName('Close comments');close.clicked.connect(self.close)
        close.setStyleSheet('padding:0;font-size:20px;')
        head.addWidget(close);layout.addWidget(self.caption)
        row=QHBoxLayout()
        art=MotionIcon('Activity',size=64);self.ambient.subscribe(art,2);row.addWidget(art)
        filename=label(Path(filepath).name,'section',True);filename.setToolTip(filepath);row.addWidget(filename,1)
        layout.addLayout(row)
        history_card,history_layout=card()
        self.history=QScrollArea();self.history.setWidgetResizable(True)
        self.history.setAccessibleName('Shared file discussion')
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history.setAutoFillBackground(False)
        self.history.viewport().setAutoFillBackground(False)
        round_surface(self.history)
        self.history_wheel=SmoothWheel(self.history)
        history_layout.addWidget(self.history);layout.addWidget(history_card,1)
        composer,body=card()
        self.author=QLineEdit(getpass.getuser());self.author.setPlaceholderText('Your name');self.author.setMaxLength(120)
        self.author.setAccessibleName('Comment author');body.addWidget(self.author)
        self.message=QPlainTextEdit();self.message.setPlaceholderText('Write a comment…')
        self.message.setAccessibleName('New comment');self.message.setFixedHeight(105);body.addWidget(self.message)
        round_surface(self.message)
        layout.addWidget(composer)
        self.status=label('Loading shared comments…','subtitle',True);layout.addWidget(self.status)
        actions=QHBoxLayout()
        self.refresh_button=MotionButton('Refresh comments');self.refresh_button.clicked.connect(self.refresh)
        self.append_button=MotionButton('Post comment');self.append_button.setObjectName('primary');self.append_button.clicked.connect(self.append)
        actions.addWidget(self.refresh_button);actions.addStretch();actions.addWidget(self.append_button)
        layout.addLayout(actions)
        if self.sound:self.sound.wire(self)
        self.refresh()

    def eventFilter(self,obj,event):
        if obj is self.caption and event.type()==QEvent.MouseButtonPress and event.button()==Qt.LeftButton:
            handle=self.windowHandle()
            if handle:handle.startSystemMove()
            return True
        return super().eventFilter(obj,event)

    def run_task(self,fn,posted=False):
        if self.task and self.task.isRunning():return
        self.refresh_button.setEnabled(False);self.append_button.setEnabled(False)
        task=CommentTask(fn,self);self.task=task
        task.result.connect(lambda result:self.loaded(result,posted))
        task.failure.connect(self.failed)
        task.finished.connect(lambda:(self.refresh_button.setEnabled(True),self.append_button.setEnabled(True)))
        task.start()

    def refresh(self):
        self.status.setText('Loading shared comments…')
        self.run_task(lambda:load_comments(self.filepath))

    def loaded(self,result,posted=False):
        from .ui import label,card
        records,errors=result
        content=QWidget();layout=QVBoxLayout(content);layout.setContentsMargins(0,0,0,0);layout.setSpacing(12)
        for record in records:
            frame,inner=card();inner.setContentsMargins(16,12,16,12)
            try:timestamp=datetime.fromisoformat(record['created']).astimezone().strftime('%d %b · %H:%M')
            except ValueError:timestamp=record['created']
            heading=label(record['author']+' · '+timestamp,'subtitle',True)
            heading.setTextFormat(Qt.PlainText);inner.addWidget(heading)
            message=label(record['text'],wrap=True);message.setTextFormat(Qt.PlainText)
            message.setTextInteractionFlags(Qt.TextSelectableByMouse|Qt.TextSelectableByKeyboard)
            inner.addWidget(message);layout.addWidget(frame)
        if not records:layout.addWidget(label('No comments yet.','subtitle'))
        layout.addStretch()
        previous=self.history.takeWidget()
        if previous:previous.deleteLater()
        self.history.setWidget(content)
        content.setAutoFillBackground(False)
        self.status.setText('\n'.join(errors) if errors else f'{len(records)} shared comment'+('s' if len(records)!=1 else ''))
        if posted:
            self.message.clear()
            if self.sound:self.sound.play('success')
        cascade(content,0,12)

    def failed(self,message):
        self.status.setText(message)
        if self.sound:self.sound.play('error')

    def append(self):
        author,message=self.author.text(),self.message.toPlainText()
        if not author.strip() or not message.strip():
            self.failed('Enter your name and a comment.');return
        self.status.setText('Posting comment…')
        def post():
            add_comment(self.filepath,author,message,self.application)
            return load_comments(self.filepath)
        self.run_task(post,True)

    def showEvent(self,event):
        super().showEvent(event)
        if not getattr(self,'introduced',False):
            self.introduced=True;self.surface.play_intro();cascade(self.surface,0,16)

    def closeEvent(self,event):
        if self.task and self.task.isRunning():
            self.status.setText('Finishing the shared comment operation…');event.ignore();return
        self.ambient.timer.stop();self.ambient.watch.stop()
        event.accept()
