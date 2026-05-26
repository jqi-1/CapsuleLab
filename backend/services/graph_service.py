import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


GRAPH_STORAGE = Path.home() / ".capsulelab" / "graphs"


@dataclass
class GraphNode:
    id: str
    kind: str
    label: str
    file_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectGraph:
    project_id: str
    project_path: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


def _graph_path(project_id: str) -> Path:
    GRAPH_STORAGE.mkdir(parents=True, exist_ok=True)
    return GRAPH_STORAGE / f"{project_id}.json"


def _load(project_id: str) -> ProjectGraph:
    path = _graph_path(project_id)
    if path.exists():
        data = json.loads(path.read_text())
        return ProjectGraph(
            project_id=data.get("project_id", project_id),
            project_path=data.get("project_path", ""),
            nodes=[GraphNode(**n) for n in data.get("nodes", [])],
            edges=[GraphEdge(**e) for e in data.get("edges", [])],
        )
    return ProjectGraph(project_id=project_id, project_path="")


def _save(graph: ProjectGraph):
    path = _graph_path(graph.project_id)
    path.write_text(json.dumps({
        "project_id": graph.project_id,
        "project_path": graph.project_path,
        "nodes": [asdict(n) for n in graph.nodes],
        "edges": [asdict(e) for e in graph.edges],
    }, indent=2, default=str))


def index_project(project_id: str, project_path: str) -> ProjectGraph:
    graph = ProjectGraph(project_id=project_id, project_path=project_path)
    proj = Path(project_path)
    if not proj.exists():
        return graph

    config_file = proj / ".workbench" / "project.yaml"
    if config_file.exists():
        graph.nodes.append(GraphNode(
            id="config",
            kind="config",
            label="Project Config (project.yaml)",
            file_path=str(config_file),
        ))

    dockerfile = proj / "Dockerfile"
    if dockerfile.exists():
        graph.nodes.append(GraphNode(
            id="dockerfile",
            kind="dockerfile",
            label="Dockerfile",
            file_path=str(dockerfile),
        ))

    readme = proj / "README.md"
    if readme.exists():
        graph.nodes.append(GraphNode(
            id="readme",
            kind="readme",
            label="README",
            file_path=str(readme),
        ))

    notebooks_dir = proj / "notebooks"
    if notebooks_dir.exists():
        for nb in sorted(notebooks_dir.glob("*.ipynb")):
            nid = f"notebook:{nb.stem}"
            graph.nodes.append(GraphNode(
                id=nid,
                kind="notebook",
                label=nb.name,
                file_path=str(nb),
            ))

    src_dir = proj / "src"
    if src_dir.exists():
        for py in sorted(src_dir.rglob("*.py")):
            pid = f"source:{py.relative_to(proj)}"
            graph.nodes.append(GraphNode(
                id=pid,
                kind="source",
                label=str(py.relative_to(proj)),
                file_path=str(py),
            ))

    tests_dir = proj / "tests"
    if tests_dir.exists():
        graph.nodes.append(GraphNode(
            id="tests",
            kind="tests",
            label="tests/",
            file_path=str(tests_dir),
        ))

    data_dir = proj / "data"
    if data_dir.exists():
        graph.nodes.append(GraphNode(
            id="data",
            kind="data",
            label="data/",
            file_path=str(data_dir),
        ))

    models_dir = proj / "models"
    if models_dir.exists():
        graph.nodes.append(GraphNode(
            id="models",
            kind="models",
            label="models/",
            file_path=str(models_dir),
        ))

    for pf in ["requirements.txt", "pyproject.toml", "environment.yml", "package.json"]:
        p = proj / pf
        if p.exists():
            graph.nodes.append(GraphNode(
                id=f"package:{pf}",
                kind="package",
                label=pf,
                file_path=str(p),
            ))

    edges = {
        "src": ["dockerfile", "config", "readme"],
        "notebook": ["src"],
        "tests": ["src"],
    }

    node_ids = {n.id for n in graph.nodes}
    for src_id, targets in edges.items():
        if src_id in node_ids:
            for t in targets:
                if t in node_ids:
                    graph.edges.append(GraphEdge(source=src_id, target=t, kind="depends_on"))

    _save(graph)
    return graph


def get_graph(project_id: str) -> ProjectGraph:
    return _load(project_id)


def summary(project_id: str, project_path: str) -> dict:
    graph = _load(project_id)
    if not graph.nodes:
        graph = index_project(project_id, project_path)

    proj = Path(project_path)
    kinds: dict[str, list[str]] = {}
    for node in graph.nodes:
        kinds.setdefault(node.kind, []).append(node.label)

    config_text = ""
    config_file = proj / ".workbench" / "project.yaml"
    if config_file.exists():
        config_text = config_file.read_text()

    return {
        "project_id": project_id,
        "project_name": proj.name,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "components": {k: len(v) for k, v in kinds.items()},
        "notebooks": kinds.get("notebook", []),
        "source_files": kinds.get("source", []),
        "config": config_text,
        "has_dockerfile": "dockerfile" in kinds,
        "has_tests": "tests" in kinds,
        "has_readme": "readme" in kinds,
        "has_data": "data" in kinds,
        "has_models": "models" in kinds,
    }
