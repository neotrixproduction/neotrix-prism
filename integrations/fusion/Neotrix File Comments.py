"""Fusion Script > Comp > Neotrix File Comments (also Resolve Fusion)."""
import os
import subprocess
ROOT = r"NEOTRIXROOT"
host = globals().get('fusion') or globals().get('fu')
composition = globals().get('comp') or (host.GetCurrentComp() if host else None)
filepath = composition.GetAttrs().get('COMPS_FileName', '') if composition else ''
if not filepath or not os.path.isfile(filepath):
    print('Save the composition as a .comp file before opening shared comments. For an unsaved Resolve composition, comment on its saved project/export in Prism.')
else:
    subprocess.Popen([os.path.join(ROOT, 'runtime', 'pythonw.exe'), os.path.join(ROOT, 'launch.py'),
                      '--comments', filepath, '--comment-app', 'Fusion'], creationflags=0x08000000)
