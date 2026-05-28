import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from capsulelab.db.repositories import projects, runs
from capsulelab.services import doctor_service, graph_service, project_service

AGENT_STORAGE = Path.home() / ".capsulelab" / "agent"


@dataclass
class AgentContext:
    project_id: str
    project_name: str
    project_path: str
    summary: str = ""
    architecture: str = ""
    setup_steps: list[str] = field(default_factory=list)
    check_results: list[dict] = field(default_factory=list)
    known_issues: list[dict] = field(default_factory=list)
    recent_runs: list[dict] = field(default_factory=list)
    app_list: list[dict] = field(default_factory=list)
    data_mounts: list[dict] = field(default_factory=list)
    secret_refs: list[dict] = field(default_factory=list)
    graph_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentAction:
    id: str
    project_id: str
    action_type: str
    title: str
    rationale: str
    files: list[str] = field(default_factory=list)
    status: str = "proposed"
    reviewer: str = ""
    review_note: str = ""


def build_project_context(project_id: str) -> AgentContext:
    row = projects.get(project_id)
    if not row:
        raise ValueError(f"Project '{project_id}' not found")

    config = project_service.load_config(row["path"])
    ctx = AgentContext(
        project_id=project_id,
        project_name=config.name,
        project_path=row["path"],
    )

    g = graph_service.get_graph(project_id)
    if not g.nodes:
        g = graph_service.index_project(project_id, row["path"])

    ctx.graph_summary = g.summary or graph_service.summary(project_id, row["path"])
    ctx.architecture = _architecture_summary(g)

    ctx.setup_steps = _setup_steps(project_id, row["path"], config)
    ctx.app_list = [a.model_dump() for a in config.apps]
    ctx.data_mounts = _data_mounts(config)
    ctx.secret_refs = [secret.model_dump() for secret in config.secrets]

    try:
        report = doctor_service.project_doctor_for_path(row["path"], project_id=project_id, project_name=config.name)
        ctx.check_results = [
            {"label": c.label, "ok": c.ok, "severity": c.severity.value, "detail": c.detail, "suggestion": c.suggestion}
            for c in report.checks
        ]
        ctx.known_issues = [check for check in ctx.check_results if not check["ok"]]
    except Exception:
        pass

    try:
        all_runs = runs.list(project_id)
        ctx.recent_runs = [
            {"id": r["id"], "name": r.get("name", ""), "status": r.get("status", "unknown")} for r in all_runs[-5:]
        ]
    except Exception:
        pass

    ctx.summary = _project_summary(ctx)
    _save_context(ctx)
    return ctx


def _setup_steps(project_id: str, project_path: str, config) -> list[str]:
    steps = ["Review project config: .workbench/project.yaml"]
    if Path(project_path, "Dockerfile").exists():
        steps.append("Build image: cap build")
    steps.append("Start container: cap start")
    if config.apps:
        for app in config.apps:
            steps.append(f"Start {app.name}: cap app start {app.id}")
    steps.append("Check readiness: cap doctor")
    return steps


def _architecture_summary(graph) -> str:
    summary = graph.summary or {}
    parts = [
        f"{summary.get('node_count', len(graph.nodes))} indexed nodes",
        f"{summary.get('edge_count', len(graph.edges))} relationships",
    ]
    languages = summary.get("languages") or {}
    if languages:
        parts.append("languages: " + ", ".join(f"{name} ({count})" for name, count in sorted(languages.items())))
    hotspots = summary.get("hotspots") or []
    if hotspots:
        parts.append("hotspots: " + ", ".join(item["label"] for item in hotspots[:5]))
    risks = summary.get("risks") or []
    if risks:
        parts.append("graph risks: " + "; ".join(risks))
    return "\n".join(parts) if parts else "No indexed components"


def _data_mounts(config) -> list[dict]:
    mounts = [
        {"kind": "mount", "source": m.source, "target": m.target, "read_only": m.read_only} for m in config.mounts
    ]
    mounts.extend({"kind": "dataset", **dataset.model_dump()} for dataset in config.datasets)
    mounts.extend({"kind": "cache", **cache.model_dump()} for cache in config.caches)
    return mounts


def _project_summary(ctx: AgentContext) -> str:
    issue_count = len(ctx.known_issues)
    app_count = len(ctx.app_list)
    run_count = len(ctx.recent_runs)
    mount_count = len(ctx.data_mounts)
    return (
        f"{ctx.project_name} is a CapsuleLab project at {ctx.project_path}. "
        f"It has {app_count} app(s), {mount_count} mount/cache/dataset declaration(s), "
        f"{run_count} recent run(s), and {issue_count} known readiness issue(s)."
    )


def _save_context(ctx: AgentContext):
    AGENT_STORAGE.mkdir(parents=True, exist_ok=True)
    path = AGENT_STORAGE / f"{ctx.project_id}.json"
    path.write_text(json.dumps({"context": asdict(ctx)}, indent=2))


def get_context(project_id: str) -> AgentContext | None:
    path = AGENT_STORAGE / f"{project_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return AgentContext(**data.get("context", {}))
    except Exception:
        return None


def catalog_contexts() -> list[dict[str, Any]]:
    results = []
    for project in projects.list():
        ctx = get_context(project["id"])
        if ctx:
            ok_count = sum(1 for c in ctx.check_results if c.get("ok"))
            total_count = len(ctx.check_results)
            results.append(
                {
                    "project_id": ctx.project_id,
                    "project_name": ctx.project_name,
                    "app_count": len(ctx.app_list),
                    "checks_passing": ok_count,
                    "checks_total": total_count,
                }
            )
        else:
            results.append(
                {
                    "project_id": project["id"],
                    "project_name": project["name"],
                    "app_count": 0,
                    "checks_passing": 0,
                    "checks_total": 0,
                }
            )
    return results


def _actions_path(project_id: str) -> Path:
    return AGENT_STORAGE / f"{project_id}.actions.json"


def list_actions(project_id: str) -> list[AgentAction]:
    path = _actions_path(project_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [AgentAction(**row) for row in data.get("actions", [])]


def _save_actions(project_id: str, actions: list[AgentAction]) -> None:
    AGENT_STORAGE.mkdir(parents=True, exist_ok=True)
    _actions_path(project_id).write_text(json.dumps({"actions": [asdict(action) for action in actions]}, indent=2))


def propose_action(
    project_id: str, action_type: str, title: str, rationale: str, files: list[str] | None = None
) -> AgentAction:
    row = projects.get(project_id)
    if not row:
        raise ValueError(f"Project '{project_id}' not found")
    project_path = Path(row["path"]).resolve()
    safe_files: list[str] = []
    for file_path in files or []:
        resolved = (
            (project_path / file_path).resolve() if not Path(file_path).is_absolute() else Path(file_path).resolve()
        )
        if project_path not in [resolved, *resolved.parents]:
            raise ValueError(f"Agent action file escapes project boundary: {file_path}")
        safe_files.append(str(resolved.relative_to(project_path)))

    action = AgentAction(
        id=str(uuid4()),
        project_id=project_id,
        action_type=action_type,
        title=title,
        rationale=rationale,
        files=safe_files,
    )
    actions = list_actions(project_id)
    actions.append(action)
    _save_actions(project_id, actions)
    return action


def review_action(project_id: str, action_id: str, approved: bool, reviewer: str = "", note: str = "") -> AgentAction:
    actions = list_actions(project_id)
    for action in actions:
        if action.id == action_id:
            action.status = "approved" if approved else "rejected"
            action.reviewer = reviewer
            action.review_note = note
            _save_actions(project_id, actions)
            return action
    raise ValueError(f"Agent action '{action_id}' not found")
