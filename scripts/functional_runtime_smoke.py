"""Exercise the current source with the bundled runtime and isolated test data."""
import os
import sys
import tempfile
import time
from pathlib import Path
os.environ['NEOTRIX_DISABLE_UPDATE_CHECK']='1'

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
from neotrix_prism.storage import Settings
from neotrix_prism.ui import MainWindow

with tempfile.TemporaryDirectory(prefix='neotrix-runtime-audit-') as directory:
    root=Path(directory)
    os.environ['NEOTRIX_USER_DIR']=str(root/'prefs')
    project=root/'projects'/'Audit Project'
    project.mkdir(parents=True)
    (project/'Scene_v001.blend').write_bytes(b'indexing fixture; never opened in a creative app')
    app=QApplication.instance() or QApplication([])
    errors=[]
    sys.excepthook=lambda kind,value,trace:errors.append(str(value))
    QMessageBox.warning=lambda *args:errors.append(args[2])
    settings=Settings();settings.data.update(roots=[str(project.parent)],reduced_motion=False)
    window=MainWindow(settings);window.show()
    def wait():
        deadline=time.monotonic()+15
        while window.jobs and time.monotonic()<deadline:QTest.qWait(20)
        assert not window.jobs, 'Worker did not finish'
    wait()
    assert window.stack.currentWidget() is window.pages['Projects']
    window.open_project(str(project));wait()
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='work'))
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='other'))
    assert window.file_cards.count()==1
    for name in window.pages:
        window.navigate(name)
        window.refresh();wait()
        QTest.qWait(250)
        assert window.orb.isVisible()
    window.settings.data['reduced_motion']=True;window.apply_theme()
    window.close();app.processEvents()
    window.artwork.pool.waitForDone(5000)
    assert not errors, errors
    print('NEOTRIX_BUNDLED_RUNTIME_FUNCTIONAL_PASS',sys.version.split()[0])
