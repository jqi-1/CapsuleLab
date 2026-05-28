from capsulelab.services import graph_service


def test_index_project_builds_native_python_graph(tmp_path, monkeypatch):
    monkeypatch.setattr(graph_service, "GRAPH_STORAGE", tmp_path / "graphs")
    (tmp_path / ".workbench").mkdir()
    (tmp_path / ".workbench" / "project.yaml").write_text("name: demo\nruntime:\n  image: demo:dev\n")
    (tmp_path / "README.md").write_text("# Demo\n")
    (tmp_path / "requirements.txt").write_text("fastapi\n")
    (tmp_path / "app.py").write_text(
        "import json\n\n"
        "class Runner:\n"
        "    def run(self):\n"
        "        helper()\n\n"
        "def helper():\n"
        "    return json.dumps({'ok': True})\n"
    )

    graph = graph_service.index_project("cap-demo", str(tmp_path))
    data = graph_service.to_dict(graph)

    node_ids = {node["id"] for node in data["nodes"]}
    edges = {(edge["source"], edge["target"], edge["kind"]) for edge in data["edges"]}

    assert "file:app.py" in node_ids
    assert "symbol:app.py:Runner" in node_ids
    assert "symbol:app.py:Runner.run" in node_ids
    assert "symbol:app.py:helper" in node_ids
    assert ("file:app.py", "symbol:app.py:Runner", "contains") in edges
    assert ("symbol:app.py:Runner.run", "symbol:app.py:helper", "calls") in edges
    assert data["summary"]["node_count"] == len(data["nodes"])
    assert data["summary"]["components"]["function"] == 2
    assert data["summary"]["components"]["package"] == 1
    assert data["summary"]["languages"]["python"] >= 3
    assert "No dependency manifest found" not in data["summary"]["risks"]


def test_summary_indexes_when_cache_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(graph_service, "GRAPH_STORAGE", tmp_path / "graphs")
    (tmp_path / "main.py").write_text("def main():\n    return 1\n")

    result = graph_service.summary("cap-demo", str(tmp_path))

    assert result["project_id"] == "cap-demo"
    assert result["node_count"] >= 2
    assert result["components"]["function"] == 1


def test_search_and_inspect_return_dynamic_subgraphs(tmp_path, monkeypatch):
    monkeypatch.setattr(graph_service, "GRAPH_STORAGE", tmp_path / "graphs")
    (tmp_path / "main.py").write_text("def alpha():\n    beta()\n\ndef beta():\n    return 1\n")
    graph_service.index_project("cap-demo", str(tmp_path))

    search_result = graph_service.search("cap-demo", str(tmp_path), query="alpha")
    inspection = graph_service.inspect_node("cap-demo", str(tmp_path), "symbol:main.py:alpha", depth=1)

    assert any(node["id"] == "symbol:main.py:alpha" for node in search_result["nodes"])
    assert inspection["node"]["label"] == "alpha"
    assert any(edge["kind"] == "calls" and edge["target"] == "symbol:main.py:beta" for edge in inspection["outgoing"])
    assert any(node["id"] == "symbol:main.py:beta" for node in inspection["graph"]["nodes"])
    assert inspection["graph"]["summary"]["risks"] == []
