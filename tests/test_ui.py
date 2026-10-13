import os
import time
from pathlib import Path
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
from neotrix_prism.storage import Settings
from neotrix_prism.ui import MainWindow


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("NEOTRIX_USER_DIR", str(tmp_path / "prefs"))
    app = QApplication.instance() or QApplication([])
    root = tmp_path / "share"
    project = root / "Neotrix Demo"
    project.mkdir(parents=True)
    for filename in ("Scene_v001.blend", "Scene_v002.blend", "Poster_v001.psd", "Edit_V0001.aep", "Logo.ai", "Comp.comp"):
        (project / filename).write_bytes(b"QA indexing fixture")
    settings = Settings()
    settings.data.update(roots=[str(root)], graph_root=str(root), reduced_motion=True)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[2]))
    result = MainWindow(settings)
    result.show()
    def wait():
        deadline = time.time() + 15
        while result.jobs and time.time() < deadline:
            app.processEvents()
            QTest.qWait(10)
        assert not result.jobs
    wait()
    yield result, project, messages, wait
    result.close()
    app.processEvents()


def test_navigation_filter_favorite_theme(window):
    window, project, messages, wait = window
    assert "Workflows" not in window.nav
    assert not hasattr(window,"editor")
    window.open_project(str(project))
    wait()
    assert window.file_cards.rowCount() == 6
    combo = window.filters["application"]
    combo.setCurrentText("Blender")
    assert window.file_cards.rowCount() == 2
    window.file_cards.selectRow(0)
    window.favorite_selected()
    window.navigate("Favorites")
    assert len(window.favorite_cards.entries) == 1
    window.navigate("Settings")
    assert not hasattr(window, "theme")
    window.save_settings()
    wait()
    assert window.surface.dark
    assert not messages


def test_rounded_shell_maximize_restore(window):
    window, project, messages, wait = window
    assert window.windowFlags() & Qt.FramelessWindowHint
    assert not window.surface.mask().contains(QPoint(0, 0))
    assert window.surface.mask().contains(window.surface.rect().center())
    window.showMaximized()
    QTest.qWait(80)
    assert window.surface.mask().isEmpty()
    window.showNormal()
    QTest.qWait(80)
    assert not window.surface.mask().contains(QPoint(0, 0))
    assert not messages


def test_interrupted_page_motion_and_sidebar(window):
    from PySide6.QtCore import QAbstractAnimation
    window, project, messages, wait = window
    window.settings.data['reduced_motion'] = False
    window.apply_theme()
    window.navigate('Projects')
    window.navigate('Projects')
    window.navigate('Settings')
    QTest.qWait(450)
    assert window.stack.currentWidget() is window.pages['Settings']
    assert all(page.graphicsEffect() is None for page in window.pages.values())
    window.toggle_sidebar()
    deadline=time.time()+3
    while window.sidebar.width()!=180 and time.time()<deadline:QTest.qWait(20)
    assert window.sidebar.width() == 180
    assert all(button.text() and button.toolTip() for button in window.nav.values())
    QTest.mouseClick(window.nav['Activity'], Qt.LeftButton)
    QTest.qWait(450)
    assert window.stack.currentWidget() is window.pages['Activity']
    window.toggle_sidebar()
    QTest.qWait(450)
    deadline=time.time()+2
    while window.sidebar.width()!=76 and time.time()<deadline:QTest.qWait(20)
    assert window.sidebar.width() == 76
    assert window.selection_rail.geometry() == window.nav['Activity'].geometry()
    assert window.orb.spin.state() == QAbstractAnimation.Stopped
    assert not messages


def test_orb_cancels_busy_task_and_stops_motion(window):
    from PySide6.QtCore import QAbstractAnimation
    window, project, messages, wait = window
    window.settings.data['reduced_motion'] = False
    window.navigate('Projects')
    job = window.worker(lambda task: task.cancel.wait(3), lambda result: None)
    QTest.qWait(60)
    assert window.orb.spin.state() == QAbstractAnimation.Running
    QTest.mouseClick(window.orb, Qt.LeftButton)
    wait()
    assert job.cancel.is_set()
    assert not window.orb.busy
    assert window.orb.spin.state() == QAbstractAnimation.Stopped
    window.settings.data['reduced_motion'] = True
    window.apply_theme()
    window.orb.set_busy(True)
    assert window.orb.spin.state() == QAbstractAnimation.Stopped
    assert not window.progress_bar.isVisible()
    window.orb.set_busy(False)
    window.navigate('Projects')
    assert window.pages['Projects'].graphicsEffect() is None
    assert not messages


def test_caption_drag_and_resize_constraints(window):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    window, project, messages, wait = window
    app = QApplication.instance()
    def send(widget, kind, global_position, button, buttons):
        local = QPointF(widget.mapFromGlobal(global_position))
        event = QMouseEvent(kind, local, QPointF(global_position), button, buttons, Qt.NoModifier)
        app.sendEvent(widget, event)
    before = window.pos()
    start = window.caption.mapToGlobal(QPoint(180, 15))
    send(window.caption, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    send(window.caption, QEvent.MouseMove, start+QPoint(40,20), Qt.NoButton, Qt.LeftButton)
    send(window.caption, QEvent.MouseButtonRelease, start+QPoint(40,20), Qt.LeftButton, Qt.NoButton)
    assert window.pos() == before+QPoint(40,20)
    shell = window.centralWidget()
    start = shell.mapToGlobal(QPoint(shell.width()-4, shell.height()//2))
    send(shell, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    send(shell, QEvent.MouseMove, start-QPoint(900,0), Qt.NoButton, Qt.LeftButton)
    send(shell, QEvent.MouseButtonRelease, start-QPoint(900,0), Qt.LeftButton, Qt.NoButton)
    assert window.width() == window.minimumWidth()
    window.showMaximized()
    QTest.qWait(50)
    start = window.caption.mapToGlobal(QPoint(180,15))
    send(window.caption, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    send(window.caption, QEvent.MouseButtonRelease, start, Qt.LeftButton, Qt.NoButton)
    assert window.isMaximized()  # A single caption click must not restore the window.
    window.showNormal()
    assert not messages


def test_bundled_display_and_text_fonts(window):
    from neotrix_prism.typography import roles
    from PySide6.QtGui import QFontInfo
    window, project, messages, wait = window
    assert roles() == ('Manrope','Manrope')
    assert QFontInfo(window.page_title.font()).family() == 'Manrope'
    assert QFontInfo(window.project_search.font()).family() == 'Manrope'


def test_projects_startup_and_minimum_window(window):
    window, project, messages, wait = window
    assert set(window.pages) == {'Projects', 'Favorites', 'Activity', 'Settings'}
    assert window.stack.currentWidget() is window.pages['Projects']
    window.resize(1024,720)
    QTest.qWait(100)
    assert window.project_cards.width() > 0
    assert window.orb.isVisible()
    assert not messages


def test_page_transition_interrupt_and_reduce(window):
    from neotrix_prism.motion import SceneTransition
    window, project, messages, wait = window
    window.settings.data['reduced_motion'] = False
    window.apply_theme()
    for name in ('Favorites', 'Activity', 'Settings', 'Projects', 'Settings'):
        window.navigate(name)
        QTest.qWait(20)
    window.settings.data['reduced_motion'] = True
    window.apply_theme()
    QTest.qWait(50)
    assert not any(t.isVisible() for t in window.findChildren(SceneTransition))
    assert window.stack.currentWidget() is window.pages['Settings']
    assert window.orb.isVisible()
    assert not messages


def test_task_orb_position_is_fixed(window):
    window, project, messages, wait = window
    window.settings.data['reduced_motion'] = False
    for size in ((1360,900),(1024,720)):
        window.resize(*size)
        window.navigate('Projects')
        QTest.qWait(450)
        anchor = window.orb.mapTo(window, QPoint(42,42))
        window.worker(lambda task: task.cancel.wait(3), lambda result: None)
        window.status.setText('Long operation status with a full creative project path and detailed progress information')
        QTest.qWait(100)
        assert window.orb.mapTo(window,QPoint(42,42)) == anchor
        QTest.mouseClick(window.orb,Qt.LeftButton)
        wait()
        QTest.qWait(100)
        assert window.orb.mapTo(window,QPoint(42,42)) == anchor
    assert not messages


def test_project_shelf_keyboard_and_file_card_actions(window,monkeypatch):
    from PySide6.QtWidgets import QTableWidget,QAbstractScrollArea
    window,project,messages,wait = window
    window.navigate('Projects')
    window.browse_projects()
    assert window.project_views.isVisible() and not window.work_panel.isVisible()
    assert not window.pages['Projects'].findChildren(QTableWidget)
    window.project_cards.setFocus()
    window.project_cards.selectRow(0)
    QTest.keyClick(window.project_cards,Qt.Key_Return)
    wait()
    assert window.work_panel.isVisible() and not window.project_views.isVisible()
    window.selected_stage="other";window.browse_step="files";window.filter_files()
    window.file_cards.selectRow(0)
    QTest.keyClick(window.file_cards,Qt.Key_Down)
    assert window.selected()['path']==window.display_files[1]['path']
    opened=[]
    monkeypatch.setattr(window,'open_path',lambda path,application=None:opened.append(path))
    QTest.keyClick(window.file_cards,Qt.Key_Return)
    assert opened==[window.selected()['path']]
    for view in window.findChildren(QAbstractScrollArea):
        assert view.verticalScrollBarPolicy()==Qt.ScrollBarAlwaysOff
        assert view.horizontalScrollBarPolicy()==Qt.ScrollBarAlwaysOff
        assert not view.mask().contains(QPoint(0,0))
    window.project_search.setText('Demo')
    assert window.project_views.isVisible() and not window.work_panel.isVisible()
    assert window.project_cards.rowCount()==1
    assert not messages


def test_uniform_grid_spacing_and_pointer(window):
    window,project,messages,wait=window
    grid=window.project_cards
    grid.set_entries([{'name':f'Project {i}','path':f'/fixture/{i}'} for i in range(12)])
    window.navigate('Projects');window.browse_projects()
    QTest.qWait(40);grid.repaint()
    top=min(rect.top() for _,rect in grid.hit_boxes)
    first=[rect for i,rect in grid.hit_boxes if rect.top()==top]
    assert len(first)>1
    assert first[0].left()==24
    for left,right in zip(first,first[1:]):assert right.left()-left.right()==pytest.approx(20)
    opened=[]
    grid.activated.disconnect();grid.activated.connect(opened.append)
    QTest.mouseClick(grid,Qt.LeftButton,pos=first[0].center().toPoint())
    assert opened==[0]
    assert not messages


def test_named_version_stage_navigation_and_multiselect(window):
    window,project,messages,wait=window
    for relative in ('03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/NTX_Vertical_0010_v001.blend',
                     '03_PRODUCTION/WORK/3D/ASSETS/projects/NTX_Vertical_0010_v001.blend',
                     '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/COMPOSITING/projects/NTX_Vertical_0010_v001.aep'):
        file=project/relative;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(b'fixture')
    window.open_project(str(project));wait()
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='work'))
    assert window.browse_step=='versions'
    assert {e['name'] for e in window.choice_cards.entries}=={'General','Vertical'}
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['name']=='Vertical'))
    assert window.browse_step=='stages'
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='unassigned'))
    assert window.file_cards.rowCount()==1
    assert window.display_files[0]['name']=='NTX_Vertical_0010_v001.blend'
    old=window.stage_document['fingerprint']
    window.stage_document=window.stage_store.save([window.display_files[0]['path']],'lighting',old)
    window.filter_files()
    assert window.file_cards.rowCount()==0
    window.breadcrumb_clicked('stages')
    assert window.browse_step=='stages'
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='lighting'))
    assert window.file_cards.rowCount()==1
    window.breadcrumb_clicked('versions')
    assert window.browse_step=='versions'
    assert not messages


def test_template_stages_and_all_stages_view(window):
    window,project,messages,wait=window
    shot='03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/'
    for relative in (shot+'MODELLING/NTX_Vertical_0010_v001.blend',shot+'LAYOUT/NTX_Vertical_0010_v002.blend',
                     shot+'LIGHTING/NTX_Vertical_0010_v003.blend',shot+'FX/NTX_Vertical_0010_v004.blend'):
        file=project/relative;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(b'fixture')
    window.open_project(str(project));wait()
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='work'))
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['name']=='Vertical'))
    paths=[e['path'] for e in window.choice_cards.entries]
    # ALL leads; every template stage is offered; empty Unassigned stays hidden.
    assert paths==['all','modelling','rigging','layout','animation','fx','lighting','compositing','other']
    window.choice_selected(paths.index('fx'))
    assert [f['name'] for f in window.display_files]==['NTX_Vertical_0010_v004.blend']
    window.breadcrumb_clicked('stages')
    window.choice_selected(0)
    assert window.page_title.text()=='All stages'
    assert [f['folder'] for f in window.display_files]==['FX','LIGHTING','LAYOUT','MODELLING']
    assert [f['stage_title'] for f in window.display_files]==['FX','Lighting','Layout','Modelling']
    window.file_cards.selectRow(0)
    assert window.selected()['path'].endswith('NTX_Vertical_0010_v004.blend')
    assert not messages


def test_bulk_stage_assignment_and_long_file_list(window):
    window,project,messages,wait=window
    window.open_project(str(project));wait()
    window.selected_stage='other';window.browse_step='files';window.filter_files()
    window.file_cards.selectAll()
    assert len(window.file_cards.selected_files())==6
    assert window.assign_button.isEnabled()
    window.apply_stage(window.file_cards.selected_files(),'layout');wait()
    assert window.file_cards.rowCount()==0
    window.selected_stage='layout';window.filter_files()
    assert window.file_cards.rowCount()==6
    assert all(window.stage_store.stage(f,window.stage_document)=='layout' for f in window.display_files)
    records=[{**window.display_files[0],'name':f'File {i}.blend','path':f'/fixture/{i}.blend'} for i in range(1000)]
    window.file_cards.set_entries(records)
    window.file_cards.selectRow(999);QTest.qWait(30)
    assert window.file_cards.currentRow()==999
    assert window.file_cards.visualItemRect(window.file_cards.item(999)).intersects(window.file_cards.viewport().rect())
    QTest.keyClick(window.file_cards,Qt.Key_Home)
    assert window.file_cards.currentRow()==0
    assert not messages


def test_refresh_library_does_not_reopen_previous_project(window):
    window,project,messages,wait=window
    window.open_project(str(project));wait()
    window.browse_projects()
    window.refresh();wait()
    assert window.project_views.isVisible()
    assert not window.work_panel.isVisible()
    assert not messages


def test_refresh_available_every_page_and_settings_menu(window):
    from neotrix_prism.motion import MotionButton
    window,project,messages,wait=window
    for name in window.pages:
        window.navigate(name)
        assert window.orb.isVisible() and window.orb.text()=='Refresh'
        QTest.mouseClick(window.orb,Qt.LeftButton);wait()
        assert window.stack.currentWidget() is window.pages[name]
        assert window.orb.isVisible() and window.orb.text()=='Refresh'
    buttons=[b for b in window.findChildren(MotionButton) if b.text()=='Prism tools']
    assert len(buttons)==1
    assert window.pages['Settings'].isAncestorOf(buttons[0])
    assert {a.text() for a in buttons[0].menu().actions()}=={'Save New Version','Prism managed-project browser','State Manager','Prism project settings'}
    assert not messages


def test_file_actions_and_activity_targets(window, monkeypatch):
    from neotrix_prism import apps
    from neotrix_prism.storage import activity
    from PySide6.QtWidgets import QFileDialog
    window,project,messages,wait=window
    window.open_project(str(project));wait()
    window.selected_stage='other';window.browse_step='files';window.filter_files()
    window.file_cards.selectRow(0)
    selected=window.selected()
    calls=[]
    monkeypatch.setattr(apps,'open_file',lambda *args:calls.append(args))
    window.open_selected()
    assert calls[-1][:2]==(selected['path'],selected['application'])
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args:(str(project/'custom.exe'),''))
    window.open_with()
    assert calls[-1][-1]==str(project/'custom.exe')
    revealed=[]
    monkeypatch.setattr(apps,'reveal',revealed.append)
    window.reveal_selected()
    assert revealed==[selected['path']]
    window.copy_selected()
    assert QApplication.clipboard().text()==selected['path']
    window.favorite_selected();window.navigate('Favorites')
    opened=[]
    monkeypatch.setattr(window,'open_path',lambda *args:opened.append(args[0]))
    window.open_favorite(0)
    assert opened==[selected['path']]
    window.remove_favorite(0)
    assert not window.favorite_cards.entries
    activity('File opened',path=selected['path'],application=selected['application'])
    window.navigate('Activity')
    assert window.activity_list.count()>0
    window.open_activity(0)
    assert opened[-1]==selected['path']
    assert not messages


def test_project_sections_assets_preview_and_back(window):
    window,project,messages,wait=window
    fixtures=('03_PRODUCTION/WORK/3D/ASSETS/projects/Shared_v001.blend',
              '03_PRODUCTION/WORK/3D/ASSETS/textures/Wood.png',
              '03_PRODUCTION/INPUT/CLIENT_ASSETS/logos/Client.svg',
              '03_PRODUCTION/INPUT/CLIENT_ASSETS/fonts/Client.otf',
              '03_PRODUCTION/INPUT/CLIENT_ASSETS/brand_guidelines/Guide.pdf',
              '02_PREPRODUCTION/brief/Brief.pdf',
              '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/LAYOUT/NTX_Vertical_0010_v001.blend',
              '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/RENDERS/v001/preview/Shot.mp4',
              '03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/RENDERS/v001/beauty/Frame.exr',
              '05_DELIVERY/REVIEW/v001/Full.MOV')
    for relative in fixtures:
        file=project/relative;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(b'fixture')
    window.open_project(str(project));wait()
    assert window.browse_step=='sections'
    assert [e['name'] for e in window.choice_cards.entries]==['Assets','Versions','Preview']
    window.choice_selected(0)
    assert window.browse_step=='collections'
    assert {'Fonts','Logos','Design guide','Brief'} <= {e['name'] for e in window.choice_cards.entries}
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='logos'))
    assert [f['name'] for f in window.display_files]==['Client.svg']
    assert window.page_title.text()=='Logos'
    window.refresh();wait()
    assert window.selected_collection=='logos' and len(window.display_files)==1
    window.browse_back()
    assert window.browse_step=='collections'
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='brief'))
    assert [f['name'] for f in window.display_files]==['Brief.pdf']
    window.browse_back();window.browse_back()
    assert window.browse_step=='sections'
    window.choice_selected(2)
    assert [e['name'] for e in window.choice_cards.entries]==['Full preview','Per-shot preview']
    window.choice_selected(0)
    assert [f['name'] for f in window.display_files]==['Full.MOV']
    window.browse_back();window.choice_selected(1)
    assert [f['name'] for f in window.display_files]==['Shot.mp4']
    window.browse_back();window.browse_back();window.choice_selected(1)
    assert {e['name'] for e in window.choice_cards.entries}=={'General','Vertical'}
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['name']=='General'))
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='modelling'))
    assert [f['name'] for f in window.display_files]==['Shared_v001.blend']
    window.breadcrumb_clicked('sections')
    window.browse_back()
    assert window.project_views.isVisible()
    window.open_project(str(project));wait()
    assert window.browse_step=='sections'
    assert not messages


def test_sections_without_named_versions_preserve_legacy_work(window):
    window,project,messages,wait=window
    window.resize(1024,720)
    window.open_project(str(project));wait()
    assert [e['name'] for e in window.choice_cards.entries]==['Assets','Working files','Preview']
    window.choice_selected(1)
    assert window.browse_step=='stages'
    window.browse_back()
    assert window.browse_step=='sections'
    window.choice_selected(0)
    assert not window.display_files
    window.breadcrumb_clicked('sections')
    window.choice_selected(2)
    assert not window.display_files
    assert not messages


def test_preview_cards_have_equal_base_geometry_and_no_department_filter(window):
    from neotrix_prism.motion import MotionButton
    window,project,messages,wait=window
    assert 'department' not in window.filters
    symbols={control.objectName():control.text() for control in window.caption.findChildren(MotionButton)}
    assert symbols['windowMinimize']=='−'
    assert symbols['windowMaximize']=='+'
    assert symbols['windowClose']=='×'
    window.open_project(str(project));wait()
    window.choice_selected(next(i for i,e in enumerate(window.choice_cards.entries) if e['path']=='preview'))
    grid=window.choice_cards
    for width in (1024,1160,1360):
        window.resize(width,900);QTest.qWait(40)
        rects=grid.card_rects()
        assert len(rects)==2
        assert rects[0].width()==pytest.approx(rects[1].width())
        assert rects[0].height()==rects[1].height()
        if grid.columns()>=2:
            assert rects[0].top()==rects[1].top()
            assert rects[1].left()-rects[0].right()==pytest.approx(20,abs=1)
    assert not messages
