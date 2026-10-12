"""Record actual Qt interaction frames; all fixtures and preferences remain local."""
import json
import os
import sys
import shutil
import subprocess
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
from neotrix_prism.motion import MotionButton

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
              "resize_result":getattr(window.resize_frame,'resize_result',None),
              "shelf_offset":window.project_cards.offset,"shelf_target":window.project_cards.target,
              "shelf_selected":window.project_cards.selected_index,"shelf_shelf":window.project_cards.shelf,
              "reduced_motion":window.settings.data['reduced_motion']}))
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

project_control = next(b for b in tiles[0].findChildren(MotionButton) if b.text() == 'Open projects')
actions = [(0, lambda: window.navigate('Home'), 'Staggered Home reveal'),
           (1000, lambda: (hover(tiles[0], True), tiles[0].track_pointer(tiles[0].rect().center())), 'Project tile expansion'),
           (1600, lambda: tiles[0].track_pointer(tiles[0].rect().topRight()), 'Pointer lighting and artwork parallax'),
           (2300, lambda: (hover(tiles[0], False), hover(tiles[1], True)), 'Workflow tile spring'),
           (3000, lambda: (hover(tiles[1], False), window.toggle_sidebar()), 'Sidebar collapse'),
           (3700, lambda: QTest.mouseClick(project_control, Qt.LeftButton), 'Tile-to-page expansion'),
           (4800, lambda: window.project_cards.scroll_to(0), 'Project shelf depth and edge fade'),
           (5700, lambda: window.project_cards.scroll_to(2), 'Project shelf spring scroll'),
           (6500, lambda: window.open_project(str(project)), 'Project scan and file card gallery'),
           (7400, lambda: window.file_cards.selectRow(0), 'File card selection and details'),
           (8000, lambda: QTest.mouseMove(window.file_cards,window.file_cards.rect().center()), 'Card hover depth'),
           (9000, lambda: window.file_cards.scroll_to(window.file_cards.limit()), 'File gallery scrolling'),
           (9800, lambda: window.file_cards.selectRow(window.file_cards.rowCount()-1), 'Last file card'),
           (10800, lambda: window.file_cards.selectRow(0), 'Keyboard-style return to first card'),
           (11700, lambda: window.navigate('Workflows'), 'Directional workflow transition'),
           (12500, window.toggle_sidebar, 'Sidebar expand'),
           (13200, lambda: window.navigate('Home'), 'Return and staggered introduction'),
           (14300, busy, 'Task orb morph and dual progress ring'),
           (15800, lambda: QTest.mouseClick(window.orb, Qt.LeftButton), 'Task cancellation')]

def capture():
    elapsed = clock.elapsed()
    while actions and elapsed >= actions[0][0]:
        timestamp, action, title = actions.pop(0)
        action()
        events.append({"ms": elapsed, "event": title})
    if '--performance' in sys.argv:
        times.append(elapsed)
        if elapsed >= 17000:
            timer.stop()
            gaps = sorted(b-a for a,b in zip(times,times[1:]))
            (output/'responsiveness.json').write_text(json.dumps({'ticks':len(times),'duration_ms':elapsed,
                'median_gap_ms':gaps[len(gaps)//2],'p95_gap_ms':gaps[int(len(gaps)*.95)],
                'max_gap_ms':max(gaps),'events':events},indent=2))
            window.close()
            app.quit()
        return
    pixmap = window.grab()
    pixels = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    image = Image.frombytes('RGBA', (pixels.width(), pixels.height()), bytes(pixels.constBits()),
                            'raw', 'BGRA', pixels.bytesPerLine(), 1)
    image.thumbnail((960, 640), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (image.width + 32, image.height + 32), '#19151e')
    canvas.paste(image, (16, 16), image)
    frames.append(canvas)
    times.append(elapsed)
    if elapsed >= 17000:
        timer.stop()
        durations = [max(20, b-a) for a,b in zip(times, times[1:])] + [50]
        frames[0].save(output/'neotrix-motion.gif', save_all=True, append_images=frames[1:],
                       duration=durations, loop=0, optimize=False)
        for ms in (400, 1400, 1900, 3900, 5300, 7800, 9600, 13800, 15000):
            index = min(range(len(times)), key=lambda i:abs(times[i]-ms))
            frames[index].save(output/f'frame-{ms}.png')
        # Encode the original RGB captures, not the palette-limited GIF, so
        # the video preserves gradient quality and actual capture timestamps.
        ffmpeg = shutil.which('ffmpeg')
        if ffmpeg:
            video_frames = output/'video-frames'
            video_frames.mkdir(exist_ok=True)
            manifest = []
            for i, (frame, duration) in enumerate(zip(frames, durations)):
                filename = f'frame-{i:04d}.png'
                frame.save(video_frames/filename, compress_level=1)
                manifest.extend([f"file '{filename}'",f'duration {duration/1000:.6f}'])
            manifest.append(f"file 'frame-{len(frames)-1:04d}.png'")
            playlist = video_frames/'frames.txt'
            playlist.write_text('\n'.join(manifest))
            subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0',
                '-i',str(playlist),'-fps_mode','vfr','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
                '-movflags','+faststart',str(output/'neotrix-motion.mp4')],check=True)
        (output/'report.json').write_text(json.dumps({'frames':len(frames),'duration_ms':elapsed,
                       'timestamps':times,'events':events,'spin_stopped': window.orb.spin.state()==QAbstractAnimation.Stopped,
                       'jobs_remaining':len(window.jobs),'size':[window.width(),window.height()]},indent=2))
        window.close()
        app.quit()

timer = QTimer()
timer.setInterval(16 if '--performance' in sys.argv else 50)
timer.timeout.connect(capture)
clock.start()
timer.start()
app.exec()
