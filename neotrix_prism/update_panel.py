"""Non-blocking release checks and explicit install/restart controls."""
import json
import threading
from pathlib import Path
from PySide6.QtCore import QTimer, QThread, Signal
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QProgressBar, QCheckBox
from . import updater, __version__
from .storage import user_dir, atomic_json


class UpdateTask(QThread):
    result = Signal(object)
    failure = Signal(str)
    progress = Signal(int,int)

    def __init__(self, fn, parent):
        super().__init__(parent)
        self.fn, self.cancel = fn, threading.Event()

    def run(self):
        try:
            self.result.emit(self.fn(self))
        except Exception as exc:
            self.failure.emit(str(exc))


class UpdatePanel:
    def __init__(self, window, layout):
        from .ui import card, label, button
        self.window=window
        self.root=Path(__file__).resolve().parents[1]
        self.release=self.prepared=self.task=None
        self.queued = False
        self.automatic=False
        frame, inner=card()
        inner.addWidget(label('App updates','section'))
        self.status=label('Version '+__version__+' · Neotrix GitHub releases','subtitle',True)
        inner.addWidget(self.status)
        self.check=button('Check for updates',self.check_now)
        self.install=button('Download update',self.download,True)
        self.install.hide()
        self.restart=button('Update & restart',lambda:self.apply(True),True)
        self.later=button('Install on close',lambda:self.apply(False))
        self.restart.hide();self.later.hide()
        self.cancel=button('Cancel download',self.cancel_download)
        self.cancel.hide()
        self.progress=QProgressBar();self.progress.hide()
        inner.addWidget(self.progress)
        row=QHBoxLayout()
        for item in (self.check,self.install,self.restart,self.later,self.cancel):row.addWidget(item)
        inner.addLayout(row)
        self.notice=label('Downloads include preview releases. Settings and project storage stay separate from the app.','subtitle',True)
        inner.addWidget(self.notice)
        layout.addWidget(frame)
        if not updater.portable_root(self.root):
            self.notice.setText('Development checkout: checks are available; installation is enabled only in portable Windows packages.')
        self.restore_pending()

    def restore_pending(self):
        record=user_dir()/'updates'/'pending.json'
        try:
            data=json.loads(record.read_text(encoding='utf-8'))
            if Path(data['root']).resolve()==self.root and Path(data['payload']).is_dir():
                self.prepared=data
                self.ready(data)
        except (OSError,ValueError,KeyError,TypeError):pass
        # Last helper result is visible after a restart or failed replacement.
        results=sorted((user_dir()/'updates').glob('job-*/result.json'),key=lambda p:p.stat().st_mtime)
        if results:
            try:
                data=json.loads(results[-1].read_text(encoding='utf-8-sig'))
                if data.get('state')=='failed':self.status.setText('Previous update failed: '+data['message'])
            except (OSError,ValueError,KeyError):pass

    def start(self, fn, callback):
        if self.task and self.task.isRunning():return
        self.check.setEnabled(False)
        task=UpdateTask(fn,self.window);self.task=task
        task.result.connect(callback)
        task.failure.connect(self.failed)
        task.progress.connect(self.advance)
        task.finished.connect(lambda:self.check.setEnabled(True))
        task.start()

    def check_now(self, automatic=False):
        self.automatic=automatic
        self.status.setText('Checking Neotrix GitHub releases…')
        self.start(lambda task:updater.latest_release(__version__),self.checked)

    def checked(self, release):
        self.release=release
        if not release:
            self.status.setText('Up to date · Version '+__version__)
            self.install.hide();return
        self.status.setText('Available: '+release['tag'])
        self.install.show()
        self.install.setEnabled(updater.portable_root(self.root))
        note=(release.get('notes') or 'New Neotrix release available.')[:700]
        if not updater.portable_root(self.root):
            note='Development checkout: installation is available only in portable builds. '+note
        self.notice.setText(note)
        if self.automatic:
            self.window.status.setText('Update available: '+release['tag']+' · Open Settings to install')
        self.window.sound.play('done')

    def download(self):
        if not self.release or (self.task and self.task.isRunning()):return
        self.automatic=False
        self.install.setEnabled(False);self.cancel.show();self.progress.show()
        self.status.setText('Downloading and verifying '+self.release['tag']+'…')
        self.start(lambda task:updater.prepare(self.release,self.root,task.cancel,
                                              lambda count,total:task.progress.emit(count//1024,total//1024)),self.ready)

    def advance(self,count,total):
        self.progress.setRange(0,total or 0);self.progress.setValue(count)

    def ready(self,prepared):
        self.prepared=prepared
        atomic_json(user_dir()/'updates'/'pending.json',prepared)
        self.cancel.hide();self.progress.hide();self.install.hide()
        self.restart.show();self.later.show()
        self.status.setText('Verified update ready: '+prepared['version'])
        self.notice.setText('Update & restart closes Prism and installs the update. Install on close waits until you close Prism; reopen it when ready. Active saves must finish first.')
        self.window.sound.play('success')

    def cancel_download(self):
        if self.task:self.task.cancel.set()
        self.status.setText('Cancelling download…')

    def failed(self,message):
        self.cancel.hide();self.progress.hide()
        self.install.setEnabled(updater.portable_root(self.root))
        self.status.setText(message)
        if not self.automatic:self.window.sound.play('error')

    def apply(self,restart):
        if self.window.jobs:
            self.status.setText('Finish or cancel the current app operation before updating.');return
        if not restart:
            self.queued = True
            self.restart.setEnabled(False);self.later.setEnabled(False)
            self.status.setText('Update scheduled for when you close Prism. Reopen the app when ready.')
            return
        try:
            status=updater.apply_on_exit(self.prepared,restart)
            (user_dir()/'updates'/'pending.json').unlink(missing_ok=True)
        except Exception as exc:
            self.failed(str(exc));return
        self.restart.setEnabled(False);self.later.setEnabled(False)
        self.status.setText('Update will install when Prism closes.')
        if restart:self.window.close()

    def can_close(self):
        if self.task and self.task.isRunning():
            self.task.cancel.set()
            self.status.setText('Cancelling update task. Close again when it finishes.')
            return False
        if self.queued:
            try:
                updater.apply_on_exit(self.prepared,False)
                (user_dir()/'updates'/'pending.json').unlink(missing_ok=True)
                self.queued=False
            except Exception as exc:
                self.failed(str(exc));return False
        return True
