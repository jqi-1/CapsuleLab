from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from backend.services import graph_service, project_service, doctor_service
from backend.db.sqlite import get_project, list_projects


AGENT_STORAGE = Path.home() / ".capsulelab" / "agent"
AGENT_STORAGE.mkdir(parents=True, exist_ok=True)


@dataclass
class AgentContext:
    project_id: str
    project_name: str
    project_path: str
    architecture: str = ""
    setup_steps: list[str] = field(default_factory=list)
    check_results: list[dict] = field(default_factory=list)
    recent_runs: list[dict] = field(default_factory=list)
    app_list: list[dict] = field(default_factory=list)


def build_project_context(project_id: str) -> AgentContext:
    row = get_project(project_id)
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

    comps = []
    for node in g.nodes:
        comps.append(f"  {node.kind}: {node.label}")
    ctx.architecture = "\n".join(comps) if comps else "No indexed components"

    ctx.setup_steps = _setup_steps(project_id, row["path"], config)
    ctx.app_list = [a.model_dump() for a in config.apps]

    try:
        report = doctor_service.project_doctor_for_path(row["path"], project_id=project_id, project_name=config.name)
        ctx.check_results = [
            {"label": c.label, "ok": c.ok, "severity": c.severity.value, "detail": c.detail, "suggestion": c.suggestion}
            for c in report.checks
        ]
    except Exception:
        pass

    try:
        from backend.db.sqlite import list_runs
        runs = list_runs(project_id)
        ctx.recent_runs = [{"id": r["id"], "name": r.get("name", ""), "status": r.get("status", "unknown")} for r in runs[-5:]]
    except Exception:
        pass

    _save_context(ctx)
    return ctx


def _setup_steps(project_id: str, project_path: str, config) -> list[str]:
    steps = ["1. Review project config: .workbench/project.yaml"]
    if Path(project_path, "Dockerfile").exists():
        steps.append("2. Build image: cap build")
    steps.append("3. Start container: cap start")
    if config.apps:
        for app in config.apps:
            steps.append(f"4. Start {app.name}: cap app start {app.id}")
    steps.append("5. Check readiness: cap doctor")
    return steps


def _save_context(ctx: AgentContext):
    path = AGENT_STORAGE / f"{ctx.project_id}.json"
    path.write_text(str({"context": asdict(ctx)}))  # simple json repr


def get_context(project_id: str) -> AgentContext | None:
    path = AGENT_STORAGE / f"{project_id}.json"
    if not path.exists():
        return None
    try:
        import json
        data = json.loads(path.read_text())
        return AgentContext(**data.get("context", {}))
    except Exception:
        return None


def catalog_contexts() -> list[dict[str, Any]]:
    results = []
    for project in list_projects():
        ctx = get_context(project["id"])
        if ctx:
            ok_count = sum(1 for c in ctx.check_results if c.get("ok"))
            total_count = len(ctx.check_results)
            results.append({
                "project_id": ctx.project_id,
                "project_name": ctx.project_name,
                "app_count": len(ctx.app_list),
                "checks_passing": ok_count,
                "checks_total": total_count,
            })
        else:
            results.append({
                "project_id": project["id"],
                "project_name": project["name"],
                "app_count": 0,
                "checks_passing": 0,
                "checks_total": 0,
            })
    return results
