"""Two independent processes on SMB, with isolated preference caches. One workstation."""
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from neotrix_prism.project_metadata import StageStore

if len(sys.argv)>1:
    project=Path(sys.argv[1]);stage=sys.argv[2]
    os.environ['NEOTRIX_USER_DIR']=str(ROOT/'artifacts/relay-stage-prefs'/stage)
    store=StageStore(project)
    before=store.load()
    ready=project/('ready-'+stage)
    ready.write_text('ready')
    import time
    deadline=time.time()+15
    while not (project/'start').exists() and time.time()<deadline:time.sleep(.03)
    try:
        doc=store.save([project/'Shot_v001.blend'],stage,before['fingerprint'])
        print(json.dumps({'saved':stage,'assignments':doc['assignments']}))
    except Exception as exc:
        print(json.dumps({'blocked':str(exc)}))
else:
    project=Path(r'\\NeoVault\Relay\_NEOTRIX_PRISM\QA')/datetime.now().strftime('stages-%Y%m%d-%H%M%S')
    project.mkdir(parents=True,exist_ok=False)
    clients=[subprocess.Popen([sys.executable,__file__,str(project),stage],stdout=subprocess.PIPE,text=True)
             for stage in ('layout','lighting')]
    import time
    deadline=time.time()+15
    while not all((project/('ready-'+stage)).exists() for stage in ('layout','lighting')) and time.time()<deadline:time.sleep(.05)
    assert all((project/('ready-'+stage)).exists() for stage in ('layout','lighting'))
    (project/'start').write_text('go')
    records=[json.loads(client.communicate(timeout=20)[0]) for client in clients]
    assert sum('saved' in record for record in records)==1,records
    assert sum('blocked' in record for record in records)==1,records
    document=StageStore(project).load()
    assert len(document['assignments'])==1
    store=StageStore(project)
    store.save([project/'Shot_v002.blend'],'lighting',document['fingerprint'])
    conflict=False
    try:store.save([project/'Shot_v003.blend'],'layout',document['fingerprint'])
    except RuntimeError:conflict=True
    assert conflict
    result={'processes':2,'workstations':1,'project':str(project),'results':records,'shared_labels':document['assignments'],'stale_edit_rejected':conflict}
    (ROOT/'artifacts/relay-stage-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
