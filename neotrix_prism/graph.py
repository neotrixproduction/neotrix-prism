"""Independent typed DAG planner and file-workflow runner. No arbitrary code nodes."""
import json
import os
import shutil
from pathlib import Path
from .indexer import scan, EXTENSIONS

NODES = {
    "Project Input": {"inputs": {}, "outputs": {"project": "project"}, "props": {}},
    "Find Files": {"inputs": {"project": "project"}, "outputs": {"files": "files"}, "props": {}},
    "Filter Files": {"inputs": {"files": "files"}, "outputs": {"files": "files"}, "props": {"application": "Blender", "contains": ""}},
    "Build Destination Path": {"inputs": {"project": "project"}, "outputs": {"path": "path"}, "props": {"folder": "COLLECTIONS"}},
    "Create Folder": {"inputs": {"path": "path"}, "outputs": {"path": "path"}, "props": {}},
    "Copy Files": {"inputs": {"files": "files", "path": "path"}, "outputs": {"files": "files"}, "props": {}},
    "Open Files": {"inputs": {"files": "files"}, "outputs": {"files": "files"}, "props": {}},
    "Log": {"inputs": {"files": "files"}, "outputs": {"files": "files"}, "props": {"message": "Workflow complete"}},
}


def example_graph():
    kinds = ["Project Input", "Find Files", "Filter Files", "Build Destination Path", "Create Folder", "Copy Files", "Log"]
    positions = [(30, 150), (270, 65), (510, 65), (270, 290), (510, 290), (760, 150), (1000, 150)]
    nodes = [{"id": str(i), "type": kind, "position": list(positions[i]), "props": dict(NODES[kind]["props"])} for i, kind in enumerate(kinds)]
    return {"format": 1, "name": "Collect project workfiles", "revision": 1, "nodes": nodes,
            "edges": [
                {"source": "0", "output": "project", "target": "1", "input": "project"},
                {"source": "1", "output": "files", "target": "2", "input": "files"},
                {"source": "0", "output": "project", "target": "3", "input": "project"},
                {"source": "3", "output": "path", "target": "4", "input": "path"},
                {"source": "2", "output": "files", "target": "5", "input": "files"},
                {"source": "4", "output": "path", "target": "5", "input": "path"},
                {"source": "5", "output": "files", "target": "6", "input": "files"}]}


def validate(graph):
    if not isinstance(graph, dict) or graph.get("format") != 1:
        raise ValueError("Unsupported workflow format. Expected format 1.")
    nodes = graph.get("nodes", [])
    if not nodes or len(nodes) > 500:
        raise ValueError("A workflow needs 1–500 nodes.")
    mapping = {}
    for node in nodes:
        if node.get("type") not in NODES or not isinstance(node.get("id"), str) or node["id"] in mapping:
            raise ValueError("Unknown node type or duplicate node ID.")
        if not isinstance(node.get("props", {}), dict):
            raise ValueError("Node properties must be an object.")
        mapping[node["id"]] = node
    incoming, dependencies = {}, {n: set() for n in mapping}
    for edge in graph.get("edges", []):
        source, target = edge.get("source"), edge.get("target")
        if source not in mapping or target not in mapping:
            raise ValueError("A connection references a missing node.")
        outputs = NODES[mapping[source]["type"]]["outputs"]
        inputs = NODES[mapping[target]["type"]]["inputs"]
        out, inp = edge.get("output"), edge.get("input")
        if out not in outputs or inp not in inputs or outputs[out] != inputs[inp]:
            raise ValueError("Connection types do not match.")
        key = (target, inp)
        if key in incoming:
            raise ValueError("Each input accepts one connection.")
        incoming[key] = edge
        dependencies[target].add(source)
    for identifier, node in mapping.items():
        for port in NODES[node["type"]]["inputs"]:
            if (identifier, port) not in incoming:
                raise ValueError(node["type"] + " needs its " + port + " input connected.")
    ordered = []
    while dependencies:
        ready = [n for n, deps in dependencies.items() if not deps]
        if not ready:
            raise ValueError("Workflow contains a cycle.")
        for n in ready:
            ordered.append(mapping[n])
            del dependencies[n]
        for deps in dependencies.values():
            deps.difference_update(ready)
    return ordered, incoming


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def destination_path(project, folder):
    folder = str(folder).replace("\\", "/")
    if not folder or Path(folder).is_absolute() or ":" in folder or ".." in Path(folder).parts:
        raise ValueError("Destination must be a relative project folder without parent traversal.")
    destination = Path(project) / folder
    if not inside(destination, project):
        raise ValueError("Destination is outside the selected project.")
    return destination


def plan(graph, project, cancel=None, progress=None):
    ordered, incoming = validate(graph)
    project = Path(project).resolve()
    if not project.is_dir():
        raise OSError("Reconnect the selected project before running a workflow.")
    values, actions, statuses, directories = {}, [], [], set()
    for node in ordered:
        if cancel and cancel.is_set():
            raise InterruptedError("Preview cancelled.")
        identifier, kind = node["id"], node["type"]
        props = {**NODES[kind]["props"], **node.get("props", {})}
        inputs = {port: values[(incoming[(identifier, port)]["source"], incoming[(identifier, port)]["output"])]
                  for port in NODES[kind]["inputs"]}
        result = {}
        if kind == "Project Input":
            result["project"] = project
        elif kind == "Find Files":
            index = scan(inputs["project"], cancel=cancel, progress=progress)
            if index.get("cancelled"):
                raise InterruptedError("Preview cancelled.")
            if index["errors"]:
                raise OSError("Preview could not inspect all folders: " + "; ".join(index["errors"][:3]))
            result["files"] = [f["path"] for f in index["files"] if f.get("kind", "working") == "working"]
        elif kind == "Filter Files":
            result["files"] = [f for f in inputs["files"]
                               if (props["application"] in ("", "All") or EXTENSIONS.get(Path(f).suffix.lower()) == props["application"])
                               and props["contains"].lower() in Path(f).name.lower()]
        elif kind == "Build Destination Path":
            result["path"] = destination_path(inputs["project"], props["folder"])
        elif kind == "Create Folder":
            result["path"] = inputs["path"]
            directories.add(str(inputs["path"]))
            actions.append({"node": identifier, "kind": "mkdir", "destination": str(inputs["path"])})
        elif kind == "Copy Files":
            result["files"] = []
            for source in inputs["files"]:
                if not inside(source, project):
                    raise ValueError("A source file is outside the project.")
                relative = Path(source).resolve().relative_to(project)
                target = inputs["path"] / relative
                if not inside(target, project):
                    raise ValueError("A copy destination escapes the project.")
                if inside(source, inputs["path"]):
                    continue  # Collection output must never collect itself.
                stat = Path(source).stat() if Path(source).exists() else None
                actions.append({"node": identifier, "kind": "copy", "source": source, "destination": str(target),
                                "skip": target.exists(), "size": stat.st_size if stat else None,
                                "modified_ns": stat.st_mtime_ns if stat else None})
                result["files"].append(str(target))
        elif kind == "Open Files":
            result["files"] = inputs["files"]
            actions.extend({"node": identifier, "kind": "open", "source": source} for source in inputs["files"])
        elif kind == "Log":
            result["files"] = inputs["files"]
            actions.append({"node": identifier, "kind": "log", "message": str(props["message"]), "count": len(inputs["files"])})
        for port, value in result.items():
            values[(identifier, port)] = value
        statuses.append({"id": identifier, "type": kind, "state": "ready"})
    return {"project": str(project), "actions": actions, "nodes": statuses, "graph": json.loads(json.dumps(graph))}


def execute(preview, opener, cancel=None, update=None):
    project = Path(preview["project"])
    if not project.is_dir():
        raise OSError("Project storage disconnected after preview.")
    records, failed = [], False
    if update and not (cancel and cancel.is_set()):
        action_nodes = {action["node"] for action in preview["actions"]}
        for node in preview.get("nodes", []):
            if node["id"] not in action_nodes:
                update(node["id"], "complete")
    for action in preview["actions"]:
        if cancel and cancel.is_set():
            records.append({"state": "cancelled", "message": "Stopped. Completed actions remain in the report."})
            break
        record = {**action, "state": "complete"}
        if update:
            update(action["node"], "running")
        try:
            kind = action["kind"]
            if kind == "mkdir":
                if not inside(action["destination"], project):
                    raise ValueError("Folder escaped the project after preview.")
                Path(action["destination"]).mkdir(parents=True, exist_ok=True)
            elif kind == "copy":
                source, destination = Path(action["source"]), Path(action["destination"])
                if not inside(source, project) or not inside(destination, project):
                    raise ValueError("Copy path changed after preview.")
                if destination.exists():
                    record["state"] = "skipped"
                    record["message"] = "Destination already exists."
                else:
                    stat = source.stat()
                    if (stat.st_size, stat.st_mtime_ns) != (action["size"], action["modified_ns"]):
                        raise RuntimeError("Source changed after preview. Preview the workflow again.")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    created = False
                    try:
                        with destination.open("xb") as output:
                            created = True
                            with source.open("rb") as stream:
                                while True:
                                    if cancel and cancel.is_set():
                                        raise InterruptedError("Copy cancelled.")
                                    chunk = stream.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    output.write(chunk)
                        shutil.copystat(source, destination)
                    except FileExistsError:
                        record["state"] = "skipped"
                        record["message"] = "Destination was created by another session."
                    except Exception:
                        if created:
                            destination.unlink(missing_ok=True)
                        raise
            elif kind == "open":
                if not inside(action["source"], project):
                    raise ValueError("Open path is outside the project.")
                opener(action["source"])
            elif kind != "log":
                raise ValueError("Unknown operation.")
        except Exception as exc:
            record.update(state="error", message=str(exc))
            failed = True
        records.append(record)
        if update:
            update(action["node"], record["state"])
        if failed:
            records.append({"state": "stopped", "message": "Remaining actions were not executed after this error."})
            break
    return records
