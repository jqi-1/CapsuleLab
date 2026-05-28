import ast
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from capsulelab.core.document_store import DocumentStore

GRAPH_STORAGE = Path.home() / ".capsulelab" / "graphs"
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
}
CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}
SUPPORT_EXTENSIONS = {".ipynb", ".md", ".toml", ".yaml", ".yml", ".json", ".txt"}
PACKAGE_FILES = {"requirements.txt", "pyproject.toml", "environment.yml", "environment.yaml", "package.json"}


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
    summary: dict[str, Any] = field(default_factory=dict)


def _graph_store(project_id: str) -> DocumentStore:
    GRAPH_STORAGE.mkdir(parents=True, exist_ok=True)
    return DocumentStore(GRAPH_STORAGE / f"{project_id}.json", default={})


def _load(project_id: str) -> ProjectGraph:
    data = _graph_store(project_id).read()
    if data:
        return ProjectGraph(
            project_id=data.get("project_id", project_id),
            project_path=data.get("project_path", ""),
            nodes=[GraphNode(**n) for n in data.get("nodes", [])],
            edges=[GraphEdge(**e) for e in data.get("edges", [])],
            summary=data.get("summary", {}),
        )
    return ProjectGraph(project_id=project_id, project_path="")


def _save(graph: ProjectGraph) -> None:
    _graph_store(graph.project_id).write(to_dict(graph))


def to_dict(graph: ProjectGraph) -> dict:
    return {
        "project_id": graph.project_id,
        "project_path": graph.project_path,
        "nodes": [asdict(n) for n in graph.nodes],
        "edges": [asdict(e) for e in graph.edges],
        "summary": graph.summary,
    }


def _subgraph(graph: ProjectGraph, node_ids: set[str]) -> ProjectGraph:
    nodes = [node for node in graph.nodes if node.id in node_ids]
    edges = [edge for edge in graph.edges if edge.source in node_ids and edge.target in node_ids]
    result = ProjectGraph(project_id=graph.project_id, project_path=graph.project_path, nodes=nodes, edges=edges)
    result.summary = _summarize(result)
    result.summary["risks"] = []
    return result


def _ensure_graph(project_id: str, project_path: str | None = None) -> ProjectGraph:
    graph = get_graph(project_id)
    if not graph.nodes and project_path:
        graph = index_project(project_id, project_path)
    return graph


def _iter_project_files(project_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(project_path.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.relative_to(project_path).parts):
            continue
        if path.suffix in CODE_EXTENSIONS or path.suffix in SUPPORT_EXTENSIONS or path.name == "Dockerfile":
            files.append(path)
    return files


def _language(path: Path) -> str:
    if path.suffix == ".py":
        return "python"
    if path.suffix in {".js", ".jsx"}:
        return "javascript"
    if path.suffix in {".ts", ".tsx"}:
        return "typescript"
    if path.suffix == ".ipynb":
        return "notebook"
    if path.name == "Dockerfile":
        return "docker"
    return path.suffix.lstrip(".") or "text"


def _node_id(prefix: str, value: str) -> str:
    return f"{prefix}:{value}".replace("\\", "/")


def _add_node(nodes: dict[str, GraphNode], node: GraphNode) -> None:
    nodes.setdefault(node.id, node)


def _add_edge(edges: set[tuple[str, str, str]], source: str, target: str, kind: str) -> None:
    if source != target:
        edges.add((source, target, kind))


def _module_name(project_path: Path, path: Path) -> str:
    rel = path.relative_to(project_path).with_suffix("")
    parts = [part for part in rel.parts if part != "__init__"]
    return ".".join(parts)


def _resolve_python_import(module: str, module_to_file: dict[str, str]) -> str | None:
    for candidate in [module, module.split(".")[0]]:
        if candidate in module_to_file:
            return module_to_file[candidate]
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")
    except OSError:
        return ""


def _collect_python_symbols(project_path: Path, path: Path, symbol_by_name: dict[str, list[str]]) -> None:
    rel = str(path.relative_to(project_path))
    try:
        tree = ast.parse(_read_text(path))
    except SyntaxError:
        return
    parent_stack: list[str] = []

    class Collector(ast.NodeVisitor):
        def _visit_named(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            qualname = ".".join(parent_stack + [node.name])
            symbol_id = _node_id("symbol", f"{rel}:{qualname}")
            symbol_by_name.setdefault(node.name, [])
            if symbol_id not in symbol_by_name[node.name]:
                symbol_by_name[node.name].append(symbol_id)
            parent_stack.append(node.name)
            self.generic_visit(node)
            parent_stack.pop()

        visit_ClassDef = _visit_named
        visit_FunctionDef = _visit_named
        visit_AsyncFunctionDef = _visit_named

    Collector().visit(tree)


def _index_python_file(
    project_path: Path,
    path: Path,
    nodes: dict[str, GraphNode],
    edges: set[tuple[str, str, str]],
    symbol_by_name: dict[str, list[str]],
    module_to_file: dict[str, str],
) -> None:
    rel = str(path.relative_to(project_path))
    file_id = _node_id("file", rel)
    text = _read_text(path)
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        nodes[file_id].metadata["parse_error"] = str(exc)
        return

    parent_stack: list[tuple[str, str]] = []

    class Visitor(ast.NodeVisitor):
        def _visit_definition(
            self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, kind: str, extra: dict | None = None
        ) -> None:
            qualname = ".".join([item[0] for item in parent_stack] + [node.name])
            symbol_id = _node_id("symbol", f"{rel}:{qualname}")
            metadata = {"qualname": qualname, "line": node.lineno, "language": "python"}
            if extra:
                metadata.update(extra)
            _add_node(
                nodes, GraphNode(id=symbol_id, kind=kind, label=node.name, file_path=str(path), metadata=metadata)
            )
            symbol_by_name.setdefault(node.name, [])
            if symbol_id not in symbol_by_name[node.name]:
                symbol_by_name[node.name].append(symbol_id)
            _add_edge(edges, parent_stack[-1][1] if parent_stack else file_id, symbol_id, "contains")
            parent_stack.append((node.name, symbol_id))
            self.generic_visit(node)
            parent_stack.pop()

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self._visit_definition(node, "class")

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_definition(node, "function")

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_definition(node, "function", {"async": True})

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                target_file = _resolve_python_import(alias.name, module_to_file)
                if target_file:
                    _add_edge(edges, file_id, target_file, "imports")
                else:
                    external_id = _node_id("external", alias.name.split(".")[0])
                    _add_node(
                        nodes,
                        GraphNode(
                            id=external_id,
                            kind="external",
                            label=alias.name.split(".")[0],
                            file_path="",
                            metadata={"language": "python"},
                        ),
                    )
                    _add_edge(edges, file_id, external_id, "imports")

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if not node.module:
                return
            target_file = _resolve_python_import(node.module, module_to_file)
            if target_file:
                _add_edge(edges, file_id, target_file, "imports")
            else:
                external_id = _node_id("external", node.module.split(".")[0])
                _add_node(
                    nodes,
                    GraphNode(
                        id=external_id,
                        kind="external",
                        label=node.module.split(".")[0],
                        file_path="",
                        metadata={"language": "python"},
                    ),
                )
                _add_edge(edges, file_id, external_id, "imports")

        def visit_Call(self, node: ast.Call) -> None:
            caller = parent_stack[-1][1] if parent_stack else file_id
            call_name = None
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr
            if call_name and call_name in symbol_by_name:
                candidates = symbol_by_name[call_name]
                same_file = [
                    candidate for candidate in candidates if candidate.startswith(_node_id("symbol", f"{rel}:"))
                ]
                _add_edge(edges, caller, (same_file or candidates)[0], "calls")
            self.generic_visit(node)

    Visitor().visit(tree)


def _index_javascript_file(
    project_path: Path,
    path: Path,
    nodes: dict[str, GraphNode],
    edges: set[tuple[str, str, str]],
    file_by_rel_no_ext: dict[str, str],
) -> None:
    rel = str(path.relative_to(project_path))
    file_id = _node_id("file", rel)
    text = _read_text(path)
    for match in re.finditer(r"(?:import\s+.*?\s+from\s+|import\s*\()\s*['\"]([^'\"]+)['\"]", text):
        specifier = match.group(1)
        if specifier.startswith("."):
            target = (path.parent / specifier).resolve()
            try:
                target_rel = str(target.relative_to(project_path))
            except ValueError:
                continue
            target_id = None
            for candidate in [target_rel, target_rel.rstrip("/") + "/index", target_rel]:
                if candidate in file_by_rel_no_ext:
                    target_id = file_by_rel_no_ext[candidate]
                    break
            if target_id:
                _add_edge(edges, file_id, target_id, "imports")
        else:
            package = specifier.split("/")[0] if not specifier.startswith("@") else "/".join(specifier.split("/")[:2])
            external_id = _node_id("external", package)
            _add_node(
                nodes,
                GraphNode(
                    id=external_id, kind="external", label=package, file_path="", metadata={"language": "javascript"}
                ),
            )
            _add_edge(edges, file_id, external_id, "imports")


def _summarize(graph: ProjectGraph) -> dict[str, Any]:
    components: dict[str, int] = {}
    languages: dict[str, int] = {}
    degree: dict[str, int] = {node.id: 0 for node in graph.nodes}
    for node in graph.nodes:
        components[node.kind] = components.get(node.kind, 0) + 1
        language = node.metadata.get("language")
        if language:
            languages[language] = languages.get(language, 0) + 1
    for edge in graph.edges:
        degree[edge.source] = degree.get(edge.source, 0) + 1
        degree[edge.target] = degree.get(edge.target, 0) + 1
    by_id = {node.id: node for node in graph.nodes}
    hotspots = sorted(
        [
            {
                "id": node_id,
                "label": by_id[node_id].label,
                "kind": by_id[node_id].kind,
                "degree": count,
                "file_path": by_id[node_id].file_path,
            }
            for node_id, count in degree.items()
            if node_id in by_id
        ],
        key=lambda item: item["degree"],
        reverse=True,
    )[:8]
    project_path = Path(graph.project_path)
    risks = []
    if not (project_path / "README.md").exists():
        risks.append("README.md not found")
    if not (project_path / "tests").exists():
        risks.append("tests/ directory not found")
    if not any(node.kind == "package" for node in graph.nodes):
        risks.append("No dependency manifest found")
    source_files = [
        node.label
        for node in graph.nodes
        if node.kind == "file" and node.metadata.get("language") in {"python", "javascript", "typescript"}
    ]
    notebooks = [node.label for node in graph.nodes if node.metadata.get("language") == "notebook"]
    return {
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "components": components,
        "languages": languages,
        "hotspots": hotspots,
        "risks": risks,
        "source_files": source_files,
        "notebooks": notebooks,
        "has_dockerfile": any(node.label == "Dockerfile" for node in graph.nodes),
        "has_tests": any(node.label == "tests" or node.label.startswith("tests/") for node in graph.nodes),
        "has_readme": any(node.label.lower() == "readme.md" for node in graph.nodes),
        "has_data": any(node.label == "data" or node.label.startswith("data/") for node in graph.nodes),
        "has_models": any(node.label == "models" or node.label.startswith("models/") for node in graph.nodes),
    }


def index_project(project_id: str, project_path: str) -> ProjectGraph:
    graph = ProjectGraph(project_id=project_id, project_path=str(Path(project_path).resolve()))
    proj = Path(project_path).resolve()
    if not proj.exists():
        graph.summary = _summarize(graph)
        return graph

    nodes: dict[str, GraphNode] = {}
    edges: set[tuple[str, str, str]] = set()
    files = _iter_project_files(proj)
    module_to_file: dict[str, str] = {}
    symbol_by_name: dict[str, list[str]] = {}
    file_by_rel_no_ext: dict[str, str] = {}

    for path in files:
        rel = str(path.relative_to(proj))
        file_id = _node_id("file", rel)
        language = _language(path)
        kind = "file" if path.suffix in CODE_EXTENSIONS else "package" if path.name in PACKAGE_FILES else "artifact"
        _add_node(
            nodes,
            GraphNode(
                id=file_id,
                kind=kind,
                label=rel,
                file_path=str(path),
                metadata={"language": language, "size_bytes": path.stat().st_size},
            ),
        )
        file_by_rel_no_ext[str(path.relative_to(proj).with_suffix(""))] = file_id
        if path.suffix == ".py":
            module_to_file[_module_name(proj, path)] = file_id

    for path in files:
        if path.suffix == ".py":
            _collect_python_symbols(proj, path, symbol_by_name)

    for path in files:
        if path.suffix == ".py":
            _index_python_file(proj, path, nodes, edges, symbol_by_name, module_to_file)
        elif path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            _index_javascript_file(proj, path, nodes, edges, file_by_rel_no_ext)

    graph.nodes = sorted(nodes.values(), key=lambda node: (node.kind, node.label))
    graph.edges = [
        GraphEdge(source=source, target=target, kind=kind)
        for source, target, kind in sorted(edges)
        if source in nodes and target in nodes
    ]
    graph.summary = _summarize(graph)
    _save(graph)
    return graph


def get_graph(project_id: str) -> ProjectGraph:
    return _load(project_id)


def search(project_id: str, project_path: str, query: str = "", kind: str | None = None, limit: int = 25) -> dict:
    graph = _ensure_graph(project_id, project_path)
    normalized = query.strip().lower()
    matches = []
    for node in graph.nodes:
        if kind and node.kind != kind:
            continue
        haystack = " ".join(
            [
                node.id,
                node.kind,
                node.label,
                node.file_path,
                str(node.metadata.get("qualname", "")),
                str(node.metadata.get("language", "")),
            ]
        ).lower()
        if normalized and normalized not in haystack:
            continue
        matches.append(node)
    matches = matches[: max(1, min(limit, 100))]
    ids = {node.id for node in matches}
    for edge in graph.edges:
        if edge.source in ids:
            ids.add(edge.target)
        if edge.target in ids:
            ids.add(edge.source)
    return to_dict(_subgraph(graph, ids))


def inspect_node(project_id: str, project_path: str, node_id: str, depth: int = 1) -> dict:
    graph = _ensure_graph(project_id, project_path)
    by_id = {node.id: node for node in graph.nodes}
    if node_id not in by_id:
        raise KeyError(node_id)
    depth = max(0, min(depth, 4))
    selected = {node_id}
    frontier = {node_id}
    for _ in range(depth):
        next_frontier: set[str] = set()
        for edge in graph.edges:
            if edge.source in frontier:
                next_frontier.add(edge.target)
            if edge.target in frontier:
                next_frontier.add(edge.source)
        next_frontier -= selected
        selected |= next_frontier
        frontier = next_frontier
    incoming = [edge for edge in graph.edges if edge.target == node_id]
    outgoing = [edge for edge in graph.edges if edge.source == node_id]
    return {
        "node": asdict(by_id[node_id]),
        "incoming": [asdict(edge) for edge in incoming],
        "outgoing": [asdict(edge) for edge in outgoing],
        "graph": to_dict(_subgraph(graph, selected)),
    }


def summary(project_id: str, project_path: str) -> dict:
    graph = _load(project_id)
    if not graph.nodes:
        graph = index_project(project_id, project_path)
    if not graph.summary:
        graph.summary = _summarize(graph)
    return {
        "project_id": project_id,
        "project_name": Path(project_path).name,
        **graph.summary,
    }
