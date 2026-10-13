"""Current native Qt README screenshots using fictional, isolated demo data."""
import os
import sys
import tempfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
from neotrix_prism.storage import Settings, activity, atomic_json
from neotrix_prism.ui import MainWindow

output=ROOT/'docs/screenshots/0.6'
output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='neotrix-readme-demo-') as directory:
    root=Path(directory)
    os.environ['NEOTRIX_USER_DIR']=str(root/'prefs')
    library=root/'library'
    names=['Atlas Brand Identity','Aurora Character Film','Studio Motion Series','Orbit Product Launch',
           'Luma Design Collection','Echo Music Campaign','Nova Title Sequence','Prism Photo Studio']
    for name in names:(library/name).mkdir(parents=True)
    project=library/'Aurora Character Film'
    files=[
        '03_PRODUCTION/INPUT/CLIENT_ASSETS/fonts/StudioSans.otf',
        '03_PRODUCTION/INPUT/CLIENT_ASSETS/logos/Aurora_Logo.ai',
        '03_PRODUCTION/INPUT/CLIENT_ASSETS/brand_guidelines/Aurora_Design_Guide.pdf',
        '02_PREPRODUCTION/brief/Aurora_Creative_Brief.pdf',
        '03_PRODUCTION/INPUT/CLIENT_ASSETS/product_photos/Reference.jpg',
        '03_PRODUCTION/WORK/3D/ASSETS/projects/NTX_Character_v001.blend',
        '03_PRODUCTION/WORK/3D/SHOTS/NTX_Summer_0010/PROJECTS/LAYOUT/NTX_Summer_0010_v001.blend',
        '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/LAYOUT/NTX_Vertical_0010_v001.blend',
        '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/ANIMATION/NTX_Vertical_0010_v002.blend',
        '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/LIGHTING/NTX_Vertical_0010_v003.blend',
        '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/COMPOSITING/NTX_Vertical_0010_v001.aep',
        '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/OTHERS/NTX_Vertical_0010_v001.psd',
        '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/RENDERS/v003/preview/NTX_Vertical_0010_v003.mp4',
        '05_DELIVERY/REVIEW/v002/NTX_Vertical_v002.mov',
    ]
    for relative in files:
        path=project/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'Fictional screenshot indexing fixture; never open as a creative document.')
    app=QApplication([])
    errors=[]
    sys.excepthook=lambda kind,value,trace:errors.append(str(value))
    QMessageBox.warning=lambda *args:errors.append(args[2])
    settings=Settings()
    settings.data.update(roots=[str(library)],reduced_motion=False,
                         favorites=[str(project),str(library/'Atlas Brand Identity'),str(project/files[9])])
    window=MainWindow(settings);window.resize(1360,900);window.show()
    def settle():
        deadline=time.monotonic()+15
        while window.jobs and time.monotonic()<deadline:QTest.qWait(30)
        assert not window.jobs
        window.artwork.pool.waitForDone(5000)
        QTest.qWait(1200)
    def grab(name):
        settle()
        QTest.mouseMove(window.caption,QPoint(250,12))
        QTest.qWait(650)
        assert window.grab().save(str(output/(name+'.png')))
    def choose(path):
        window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']==path))
    settle()
    window.toggle_sidebar();grab('project-library')
    window.open_project(str(project));grab('project-overview')
    choose('assets');grab('client-assets')
    window.breadcrumb_clicked('sections');choose('preview');grab('preview')
    window.breadcrumb_clicked('sections');choose('work');grab('versions')
    choose('Vertical');grab('stages')
    choose('all')
    window.file_cards.selectRow(0);grab('working-files')
    window.navigate('Favorites');grab('favorites')
    activity('New version saved',path=str(project/files[9]),application='Blender')
    activity('Stage assigned',path=str(project/files[9]),stage='lighting',count=1)
    activity('File opened',path=str(project/files[10]),application='After Effects')
    window.navigate('Activity');grab('activity')
    window.navigate('Settings')
    window.roots_edit.setPlainText(r'\\NeoVault\Relay')
    grab('settings')
    atomic_json(output/'capture.json',{'version':'0.6.0','native_qt':True,'fictional_data':True,
        'logical_size':[window.width(),window.height()],'dpr':window.devicePixelRatioF(),
        'screens':sorted(p.name for p in output.glob('*.png'))})
    window.close();app.processEvents();window.artwork.pool.waitForDone(5000)
    assert not errors,errors
    print('CURRENT_README_SCREENSHOTS_PASS',output)
