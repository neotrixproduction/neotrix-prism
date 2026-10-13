"""Local, whitelisted Adobe panel commands dispatched on Qt's main thread."""
import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from PySide6.QtCore import QObject, Signal

PORT = 16400
COMMANDS = {"connectPhotoshop", "disconnect", "saveVersion", "saveExtended", "export", "projectBrowser",
            "settings", "importMedia", "checkVersions", "render"}


class Bridge(QObject):
    command = Signal(str, str)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.command.connect(self.handle)
        bridge = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def reply(self, code, data):
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_OPTIONS(self):
                self.reply(200, {})
            def do_GET(self):
                self.reply(200, {"application": "NeotrixPrism", "status": "ready"})
            def do_POST(self):
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size < 8192:
                        raise ValueError("Invalid message size")
                    data = json.loads(self.rfile.read(size))
                    if not isinstance(data, dict):
                        raise ValueError('Expected a command object')
                    app, command = data.get("app"), data.get("command")
                    if app not in ("photoshop", "aftereffects") or command not in COMMANDS:
                        raise ValueError("Unsupported application or command")
                    bridge.command.emit(app, command)
                    self.reply(202, {"status": "queued", "command": command})
                except (ValueError, TypeError) as exc:
                    self.reply(400, {"error": str(exc)})
        self.server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def handle(self, app, command):
        if command in ("connectPhotoshop", "disconnect"):
            return  # Opening/hiding an Adobe panel never closes user documents.
        try:
            from .integration import get_core, save_version_dialog
            core = get_core("Photoshop" if app == "photoshop" else "AfterEffects")
            if command in ("saveVersion", "saveExtended"):
                save_version_dialog(core, self.window)
            elif command == "projectBrowser":
                core.neotrixBrowser()
            elif command == "settings":
                shell = core.neotrixBrowser()
                shell.navigate("Settings")
            elif command == "export":
                core.appPlugin.exportImage()
            elif command == "importMedia":
                core.appPlugin.openImportMediaDlg()
            elif command == "checkVersions":
                core.appPlugin.checkVersions()
            elif command == "render":
                core.appPlugin.openRenderDlg()
        except Exception as exc:
            self.window.error(str(exc))

    def close(self):
        self.server.shutdown()
        self.server.server_close()
