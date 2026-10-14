import copy
import json
import threading
from pathlib import Path
import pytest
from neotrix_prism import graph, indexer, versions
from neotrix_prism.storage import GraphLibrary, exclusive_lock, Settings


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("NEOTRIX_USER_DIR", str(tmp_path / "prefs"))


def fixture_project(tmp_path):
    root = tmp_path / "project"
    for file in ("03_PRODUCTION/WORK/3D/SHOTS/ABC_Landscape_0010/PROJECTS/ABC_0010_v002.blend",
                 "03_PRODUCTION/WORK/GRAPHIC_DESIGN/projects/banner_v0003.ai",
                 "04_POST/title_V010.aep", "design.psd", "large.psb", "text.aepx", "shot.comp"):
        path = root / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"working file")
    for file in ("#recycle/hidden.blend", "Auto-Save/hidden.aep", ".git/hidden.psd", "_NEOTRIX_PRISM/hidden.comp"):
        path = root / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"excluded")
    return root


def test_index_mixed_deep_exclusions(tmp_path):
    root = fixture_project(tmp_path)
    result = indexer.scan(root)
    assert len(result["files"]) == 7
    assert {f["application"] for f in result["files"]} == {"Blender", "Illustrator", "Photoshop", "After Effects", "Fusion"}
    blend = next(f for f in result["files"] if f["application"] == "Blender")
    assert (blend["variant"], blend["shot"], blend["version"], blend["department"]) == ("Landscape", "Shot 0010", "v002", "3D")
    assert not result["errors"]


def test_cache_and_cancel(tmp_path):
    root = fixture_project(tmp_path)
    indexer.scan(root)
    assert len(indexer.cached(root)["files"]) == 7
    cancel = threading.Event()
    cancel.set()
    assert indexer.scan(root, cancel)["cancelled"]
    absent = indexer.scan(tmp_path / "missing")
    assert absent["cached"] and absent["errors"]


@pytest.mark.parametrize("name,other,expected", [
    ("shot_v001.blend", "shot_v009.blend", "shot_v010.blend"),
    ("shot_V0001.aep", "shot_V0010.aep", "shot_V0011.aep"),
    ("design.psd", "design_v004.psd", "design_v005.psd"),
    ("shot_v999.psb", "different_v9999.psb", "shot_v1000.psb"),
])
def test_version_family(tmp_path, name, other, expected):
    source = tmp_path / name
    source.write_bytes(b"original")
    (tmp_path / other).write_bytes(b"previous")
    assert versions.next_version(source).name == expected


def test_version_in_memory_and_collision(tmp_path):
    source = tmp_path / "work_v001.psd"
    source.write_bytes(b"disk version")
    expected = versions.next_version(source)
    def adapter(destination):
        Path(destination).write_bytes(b"unsaved in-memory changes")
        return True
    dest = versions.save_next(source, adapter, expected)
    assert source.read_bytes() == b"disk version"
    assert dest.read_bytes() == b"unsaved in-memory changes"
    with pytest.raises(RuntimeError, match="after the preview"):
        versions.save_next(source, adapter, expected)
    with exclusive_lock(tmp_path / ".neotrix-version.lock"):
        with pytest.raises(RuntimeError):
            versions.save_next(source, adapter)
    assert not (tmp_path / ".neotrix-version.lock").exists()


def test_application_failure_releases_reservation(tmp_path):
    source = tmp_path / "work.blend"
    source.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="did not complete"):
        versions.save_next(source, lambda p: False)
    assert not (tmp_path / ".neotrix-version.lock").exists()


def test_graph_preview_execute_and_skip(tmp_path):
    root = fixture_project(tmp_path)
    document = graph.example_graph()
    preview = graph.plan(document, root)
    assert not (root / "COLLECTIONS").exists()
    assert sum(a["kind"] == "copy" for a in preview["actions"]) == 1
    result = graph.execute(preview, lambda p: None)
    assert all(r["state"] == "complete" for r in result)
    target = next(a["destination"] for a in preview["actions"] if a["kind"] == "copy")
    assert Path(target).read_bytes() == b"working file"
    new = graph.plan(document, root)
    assert sum(a["kind"] == "copy" for a in new["actions"]) == 1
    assert any(r["state"] == "skipped" for r in graph.execute(new, lambda p: None))


def test_graph_invalid_ports_cycle_and_traversal(tmp_path):
    document = graph.example_graph()
    bad = copy.deepcopy(document)
    bad["edges"][0]["output"] = "files"
    with pytest.raises(ValueError, match="types"):
        graph.validate(bad)
    cycle = {"format": 1, "nodes": [
        {"id": "a", "type": "Filter Files", "props": {}}, {"id": "b", "type": "Filter Files", "props": {}}],
        "edges": [{"source": "a", "output": "files", "target": "b", "input": "files"},
                  {"source": "b", "output": "files", "target": "a", "input": "files"}]}
    with pytest.raises(ValueError, match="cycle"):
        graph.validate(cycle)
    for path in ("../outside", "/outside", r"C:\outside"):
        with pytest.raises(ValueError):
            graph.destination_path(tmp_path, path)


def test_graph_changed_source_cancel_and_error(tmp_path):
    root = fixture_project(tmp_path)
    preview = graph.plan(graph.example_graph(), root)
    source = Path(next(a["source"] for a in preview["actions"] if a["kind"] == "copy"))
    source.write_bytes(b"changed after preview")
    result = graph.execute(preview, lambda p: None)
    assert any(r["state"] == "error" for r in result)
    assert result[-1]["state"] == "stopped"
    cancel = threading.Event()
    cancel.set()
    assert graph.execute(preview, lambda p: None, cancel)[0]["state"] == "cancelled"


def test_shared_graph_conflict_and_offline(tmp_path):
    root = tmp_path / "share"
    root.mkdir()
    library = GraphLibrary(root)
    value = graph.example_graph()
    first = library.save("example.json", value)
    assert library.list()[0]["graph"]["format"] == 1
    assert library.save("example.json", value, first) == first
    value["revision"] = 2
    second = library.save("example.json", value, first)
    assert second != first
    with pytest.raises(RuntimeError, match="changed"):
        library.save("example.json", value, first)
    # Simulate an unreachable root without relying on Windows allowing a
    # freshly scanned directory to be renamed while antivirus holds a handle.
    library.root = tmp_path / "offline-share"
    library.path = library.root / "_NEOTRIX_PRISM" / "Graphs"
    assert not library.online()
    assert library.list()
    with pytest.raises(OSError):
        library.save("other.json", value)


def test_output_files_and_permission_notice(tmp_path, monkeypatch):
    root = fixture_project(tmp_path)
    output = root / "05_DELIVERY/Review.mp4"
    output.parent.mkdir()
    output.write_bytes(b"media fixture")
    (root / "unrelated.jpg").write_bytes(b"not a project output")
    result = indexer.scan(root)
    assert len(result["files"]) == 8
    assert next(f for f in result["files"] if f["path"] == str(output))["kind"] == "output"
    original = indexer.os.walk
    def denied(*args, **kwargs):
        kwargs["onerror"](PermissionError("QA denied folder"))
        yield from original(*args, **kwargs)
    monkeypatch.setattr(indexer.os, "walk", denied)
    result = indexer.scan(root)
    assert result["errors"] == ["QA denied folder"]
    with pytest.raises(OSError, match="could not inspect"):
        graph.plan(graph.example_graph(), root)
