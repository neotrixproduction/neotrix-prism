import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from neotrix_prism.comments import add_comment, load_comments, discussion_folder
from neotrix_prism.indexer import skip_dir


@pytest.mark.parametrize('extension', ['.blend', '.comp', '.aep', '.psd', '.ai'])
def test_shared_format_and_legacy_blender(tmp_path, extension):
    file = tmp_path / ('scene' + extension)
    file.touch()
    folder = discussion_folder(file)
    folder.mkdir(parents=True)
    legacy = dict(id='legacy', author='Artist', text='Older Blender comment', created='2026-10-13T01:00:00+00:00', schema=1)
    (folder / 'old.json').write_text(json.dumps(legacy))
    add_comment(file, 'Reviewer', 'Multiline\nUnicode: bagus ✓', 'Fusion')
    comments, errors = load_comments(file)
    assert len(comments) == 2 and not errors
    assert comments[0] == legacy
    assert comments[1]['application'] == 'Fusion'
    assert file.read_bytes() == b''
    assert skip_dir(file.name + '.neotrix')


def test_parallel_append_and_corrupt_record(tmp_path):
    file = tmp_path / 'scene.aep'
    file.touch()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: add_comment(file, str(i), 'Review', 'After Effects'), range(24)))
    (discussion_folder(file) / 'bad.json').write_text('null')
    comments, errors = load_comments(file)
    assert len(comments) == 24 and len({c['id'] for c in comments}) == 24
    assert len(errors) == 1


def test_dialog_append_refresh_and_validation(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QLabel
    from PySide6.QtTest import QTest
    from neotrix_prism.comment_dialog import CommentDialog
    app = QApplication.instance() or QApplication([])
    file = tmp_path / 'scene.comp'
    file.touch()
    dialog = CommentDialog(str(file), application='Fusion')
    def wait():
        for _ in range(300):
            app.processEvents()
            if dialog.task is None or not dialog.task.isRunning():
                QTest.qWait(20)
                return
            QTest.qWait(10)
        raise AssertionError('Comment worker did not finish')
    wait()
    dialog.append()
    assert 'Enter your name' in dialog.status.text()
    dialog.message.setPlainText('Team review')
    dialog.append()
    wait()
    assert any('Team review' in label.text() for label in dialog.history.findChildren(QLabel))
    assert dialog.message.toPlainText() == ''
    add_comment(file, 'Blender artist', 'Second review', 'Blender')
    dialog.refresh()
    wait()
    assert any('Second review' in label.text() for label in dialog.history.findChildren(QLabel))
    dialog.close()
