from pathlib import Path
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from neotrix_prism.integration import save_version_dialog


class Adapter:
    def __init__(self, current):
        self.current = current
        self.saved = []
    def getCurrentFileName(self, core):
        return self.current
    def saveScene(self, core, path):
        Path(path).write_bytes(b"unsaved document state")
        self.current = path
        self.saved.append(path)
        return None  # This is the real Photoshop adapter's success return.


def test_dialog_saves_none_return_adapter(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("NEOTRIX_USER_DIR", str(tmp_path / "prefs"))
    source = tmp_path / "Poster_V0001.psd"
    source.write_bytes(b"disk state")
    adapter = Adapter(str(source))
    core = SimpleNamespace(appPlugin=adapter, requestedApp="Photoshop")
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Save)
    saved = save_version_dialog(core, expected_source=str(source))
    assert saved.name == "Poster_V0002.psd"
    assert saved.read_bytes() == b"unsaved document state"
    assert source.read_bytes() == b"disk state"


def test_active_document_changed_aborts_without_writes(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "Poster_v001.psd"
    source.write_bytes(b"original")
    adapter = Adapter(str(source))
    core = SimpleNamespace(appPlugin=adapter, requestedApp="Photoshop")
    warnings = []
    def question(*args):
        adapter.current = str(tmp_path / "Different_document.psd")
        return QMessageBox.Save
    monkeypatch.setattr(QMessageBox, "question", question)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    assert save_version_dialog(core) is None
    assert not adapter.saved
    assert "active document changed" in warnings[0]
    assert not (tmp_path / ".neotrix-version.lock").exists()


def test_selected_file_requires_same_active_document(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "Selected_v001.psd"
    source.write_bytes(b"x")
    warnings = []
    adapter = Adapter("")
    core = SimpleNamespace(appPlugin=adapter, requestedApp="Photoshop")
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    assert save_version_dialog(core, expected_source=str(source)) is None
    assert not adapter.saved and warnings


def test_save_inherits_shared_stage_only_after_success(tmp_path, monkeypatch):
    from neotrix_prism.project_metadata import StageStore
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEOTRIX_USER_DIR',str(tmp_path/'prefs'))
    source=tmp_path/'Shot_v001.psd';source.write_bytes(b'disk state')
    store=StageStore(tmp_path)
    store.save([source],'lighting',None)
    adapter=Adapter(str(source))
    core=SimpleNamespace(appPlugin=adapter,requestedApp='Photoshop')
    monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.Save)
    saved=save_version_dialog(core)
    assert store.load()['assignments'][saved.name]=='lighting'
    adapter.saveScene=lambda *args:False
    warnings=[]
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:warnings.append(args[2]))
    assert save_version_dialog(core) is None
    assert 'Shot_v003.psd' not in store.load()['assignments']
    assert warnings
