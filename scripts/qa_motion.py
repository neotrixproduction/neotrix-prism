"""Record actual Qt interaction frames; all fixtures and preferences remain local."""
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEOTRIX_USER_DIR"] = str(ROOT / "artifacts/motion-prefs")
from PySide6.QtCore import Qt, QTimer, QElapsedTimer, QPointF, QAbstractAnimation
from PySide6.QtGui import QEnterEvent, QImage
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import QEvent
from PIL import Image
from neotrix_prism.ui import MainWindow
from neotrix_prism.storage import Settings
from neotrix_prism.surfaces import GradientTile

app = QApplication([])
settings = Settings()
root = ROOT / "artifacts/visual-library"
project = root / "Neotrix Studio Film"
settings.data.update(roots=[str(root)], graph_root=str(root), reduced_motion=False,
                     recent=[str(project)], favorites=[str(project)])
window = MainWindow(settings)
window.resize(1280, 850)
window.show()
output = ROOT / "artifacts/motion-preview"
output.mkdir(parents=True, exist_ok=True)
if "--interactive" in sys.argv:
    window.setWindowTitle("Neotrix Prism — Motion QA")
    def state():
        (output / "session.json").write_text(json.dumps({"hwnd": int(window.winId()), "pid": os.getpid(),
              "position": [window.x(),window.y()], "size":[window.width(),window.height()],
              "maximized":window.isMaximized(),"minimized":window.isMinimized(),
              "move_result":getattr(window.caption,'move_result',None),
              "resize_result":getattr(window.resize_frame,'resize_result',None)}))
    monitor=QTimer();monitor.timeout.connect(state);monitor.start(200)
    state()
    app.exec()
    sys.exit(0)

def hover(widget, enter):
    if enter:
        center = QPointF(widget.rect().center())
        event = QEnterEvent(center, center, QPointF(widget.mapToGlobal(widget.rect().center())))
    else:
        event = QEvent(QEvent.Leave)
    app.sendEvent(widget, event)

tiles = [tile for tile in window.pages['Home'].findChildren(GradientTile) if tile.tone in ('Projects','Workflows','Favorites')]
frames, times, events = [], [], []
clock = QElapsedTimer()

def busy():
    window.worker(lambda task: task.cancel.wait(2), lambda result: None)
    window.status.setText("Task motion preview · QA fixture only")

actions = [(0, lambda: window.navigate('Home'), 'Home reveal'),
           (850, lambda: hover(tiles[0], True), 'Project tile lift'),
           (1500, lambda: (hover(tiles[0], False), hover(tiles[1], True)), 'Workflow tile emphasis'),
           (2200, lambda: (hover(tiles[1], False), window.toggle_sidebar()), 'Sidebar collapse'),
           (2800, lambda: QTest.mouseClick(window.nav['Projects'], Qt.LeftButton), 'Project navigation'),
           (3450, lambda: (window.open_project(str(project))), 'Project scan'),
           (4000, lambda: window.file_table.selectRow(0), 'File details reveal'),
           (4550, lambda: window.navigate('Workflows'), 'Workflow navigation'),
           (5050, window.toggle_sidebar, 'Sidebar expand'),
           (5550, lambda: window.navigate('Home'), 'Staggered tile introduction'),
           (6600, busy, 'Task progress ring'),
           (7400, lambda: QTest.mouseClick(window.orb, Qt.LeftButton), 'Task cancellation')]

def capture():
    elapsed = clock.elapsed()
    while actions and elapsed >= actions[0][0]:
        timestamp, action, title = actions.pop(0)
        action()
        events.append({"ms": elapsed, "event": title})
    pixmap = window.grab()
    pixels = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    image = Image.frombytes('RGBA', (pixels.width(), pixels.height()), bytes(pixels.constBits()),
                            'raw', 'BGRA', pixels.bytesPerLine(), 1)
    image.thumbnail((960, 640), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (image.width + 32, image.height + 32), '#19151e')
    canvas.paste(image, (16, 16), image)
    frames.append(canvas)
    times.append(elapsed)
    if elapsed >= 8500:
        timer.stop()
        durations = [max(20, b-a) for a,b in zip(times, times[1:])] + [50]
        frames[0].save(output/'neotrix-motion.gif', save_all=True, append_images=frames[1:],
                       duration=durations, loop=0, optimize=False)
        for ms in (400, 1150, 2400, 3100, 4700, 5900, 7000):
            index = min(range(len(times)), key=lambda i:abs(times[i]-ms))
            frames[index].save(output/f'frame-{ms}.png')
        (output/'report.json').write_text(json.dumps({'frames':len(frames),'duration_ms':elapsed,
                       'timestamps':times,'events':events,'spin_stopped': window.orb.spin.state()==QAbstractAnimation.Stopped,
                       'jobs_remaining':len(window.jobs),'size':[window.width(),window.height()]},indent=2))
        window.close()
        app.quit()

timer = QTimer()
timer.setInterval(50)
timer.timeout.connect(capture)
clock.start()
timer.start()
app.exec()
