"""Independent SMB clients test cooperative reservations, not a second workstation."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neotrix_prism.versions import save_next
from neotrix_prism.storage import GraphLibrary
from neotrix_prism.graph import example_graph


def worker(source):
    def save(path):
        time.sleep(.5)
        with open(path, "xb") as stream:
            stream.write(b"Neotrix reservation QA")
        return True
    try:
        result = save_next(source, save)
        print(json.dumps({"saved": result.name}))
    except Exception as exc:
        print(json.dumps({"blocked": str(exc)}))


if len(sys.argv) > 1:
    worker(sys.argv[1])
else:
    from datetime import datetime
    directory = Path(r"\\NeoVault\Relay\_NEOTRIX_PRISM\QA") / datetime.now().strftime("reservation-%Y%m%d-%H%M%S")
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / "Working_v001.psd"
    source.write_bytes(b"Neotrix reservation QA source")
    clients = [subprocess.Popen([sys.executable, str(Path(__file__)), str(source)],
                                stdout=subprocess.PIPE, text=True) for _ in range(2)]
    records = [json.loads(client.communicate(timeout=15)[0].strip()) for client in clients]
    assert sum("saved" in record for record in records) == 1, records
    assert sum("blocked" in record for record in records) == 1, records
    library = GraphLibrary(directory)
    fingerprint = library.save("qa-workflow.json", example_graph())
    assert library.list()
    doc = example_graph()
    doc["revision"] = 2
    library.save("qa-workflow.json", doc, fingerprint)
    conflict = False
    try:
        library.save("qa-workflow.json", doc, fingerprint)
    except RuntimeError:
        conflict = True
    assert conflict
    output = {"clients": 2, "workstations": 1, "reservation_results": records, "shared_graph_conflict": True}
    (ROOT / "artifacts/relay-result.json").write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))
