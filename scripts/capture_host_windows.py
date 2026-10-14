"""Capture only host windows holding this task's QA documents."""
import time
from pathlib import Path
import win32gui
import win32con
import win32ui
import ctypes
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "artifacts/host-screenshots"
output.mkdir(parents=True, exist_ok=True)
windows = []
def add(hwnd, _):
    title = win32gui.GetWindowText(hwnd)
    if win32gui.IsWindowVisible(hwnd) and ("Neotrix_QA" in title or title == "Neotrix Prism"):
        windows.append((hwnd, title))
win32gui.EnumWindows(add, None)
for i, (hwnd, title) in enumerate(windows):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(.3)
        box = win32gui.GetWindowRect(hwnd)
        if box[2] > box[0] and box[3] > box[1]:
            path = output / ("aftereffects.png" if "After Effects" in title else "desktop-host.png")
            width, height = box[2] - box[0], box[3] - box[1]
            source_dc = win32gui.GetWindowDC(hwnd)
            dc = win32ui.CreateDCFromHandle(source_dc)
            memory = dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(dc, width, height)
            memory.SelectObject(bitmap)
            result = ctypes.windll.user32.PrintWindow(hwnd, memory.GetSafeHdc(), 2)
            if result:
                info = bitmap.GetInfo()
                pixels = bitmap.GetBitmapBits(True)
                image = Image.frombuffer("RGB", (info["bmWidth"],info["bmHeight"]), pixels, "raw", "BGRX", 0, 1)
                image.save(path)
            memory.DeleteDC()
            dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, source_dc)
            win32gui.DeleteObject(bitmap.GetHandle())
            print(path.name, title[:100])
    except Exception as exc:
        print(type(exc).__name__)
