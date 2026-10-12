import json
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "artifacts/app-smoke/AfterEffects"
output.mkdir(parents=True, exist_ok=True)
source = output / "Neotrix_QA_V0001.aep"
ready = output / "ready.json"
script = output / "prepare.jsx"
script.write_text("""
app.beginSuppressDialogs();
try {
  app.newProject();
  var c = app.project.items.addComp("Neotrix QA",128,128,1,1,24);
  c.layers.addSolid([0.54,0.46,0.93],"Base",128,128,1);
  app.project.save(new File(SOURCE));
  c.layers.addText("Unsaved Neotrix QA layer");
  var id = app.findMenuCommandId("Neotrix Prism");
  if (id) app.executeCommand(id);
  var out = new File(READY);
  out.open("w");out.write('{"ready":true,"extension_command":'+id+'}');out.close();
} catch(e) {
  var out = new File(READY);out.open("w");out.write('{"error":"'+e.toString().replace(/"/g,"'")+'"}');out.close();
}
app.endSuppressDialogs(false);
""".replace("SOURCE", json.dumps(source.as_posix())).replace("READY", json.dumps(ready.as_posix())), encoding="utf-8")
subprocess.Popen([r"C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe", "-r", str(script)],
                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
print(str(ready))
