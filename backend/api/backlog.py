from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capsulelab.core.project import ProjectConfig
from capsulelab.db.repositories import projects
from capsulelab.services import (
    agent_service,
    doctor_service,
    git_service,
    graph_service,
    image_service,
    project_service,
    resource_service,
    run_service,
    secrets_service,
)

router = APIRouter()


class GitCommitRequest(BaseModel):
    message: str
    all_changes: bool = True


class GitRemoteRequest(BaseModel):
    remote: str = "origin"
    branch: str | None = None


class GitPushRequest(GitRemoteRequest):
    set_upstream: bool = False


class GitBranchRequest(BaseModel):
    branch: str
    create: bool = False


class GitPublishRequest(BaseModel):
    remote_url: str
    remote: str = "origin"
    branch: str | None = None


class AgentActionRequest(BaseModel):
    action_type: str
    title: str
    rationale: str
    files: list[str] = []


class AgentActionReviewRequest(BaseModel):
    approved: bool
    reviewer: str = ""
    note: str = ""


def _project(project_id: str) -> tuple[dict, ProjectConfig]:
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row, project_service.load_config(row["path"])


def _git_action(project_id: str, action, **kwargs):
    row, _ = _project(project_id)
    try:
        return action(row["path"], **kwargs)
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())


@router.get("/git/status")
def git_status(project_id: str):
    row, _ = _project(project_id)
    return git_service.git_status(row["path"])


@router.post("/git/init")
def git_init(project_id: str):
    return _git_action(project_id, git_service.init_repo)


@router.get("/git/history")
def git_history(project_id: str, limit: int = 10):
    return _git_action(project_id, git_service.history, limit=limit)


@router.get("/git/branches")
def git_branches(project_id: str):
    return _git_action(project_id, git_service.branches)


@router.post("/git/branches")
def git_switch_branch(project_id: str, req: GitBranchRequest):
    return _git_action(project_id, git_service.switch_branch, branch=req.branch, create=req.create)


@router.post("/git/commit")
def git_commit(project_id: str, req: GitCommitRequest):
    return _git_action(project_id, git_service.commit, message=req.message, all_changes=req.all_changes)


@router.post("/git/fetch")
def git_fetch(project_id: str, req: GitRemoteRequest):
    return _git_action(project_id, git_service.fetch, remote=req.remote)


@router.post("/git/pull")
def git_pull(project_id: str, req: GitRemoteRequest):
    return _git_action(project_id, git_service.pull, remote=req.remote, branch=req.branch)


@router.post("/git/push")
def git_push(project_id: str, req: GitPushRequest):
    return _git_action(
        project_id, git_service.push, remote=req.remote, branch=req.branch, set_upstream=req.set_upstream
    )


@router.post("/git/publish")
def git_publish(project_id: str, req: GitPublishRequest):
    return _git_action(project_id, git_service.publish, remote_url=req.remote_url, remote=req.remote, branch=req.branch)


@router.get("/secrets")
def secrets(project_id: str):
    row, config = _project(project_id)
    return {
        "configured": [secret.model_dump() for secret in config.secrets],
        "present": secrets_service.list_secret_presence(project_id),
        "missing": secrets_service.missing_required_secrets(project_id, config),
    }


@router.get("/runs")
def runs(project_id: str):
    _project(project_id)
    return run_service.list_project_runs(project_id)


@router.post("/runs")
def start_run(project_id: str, name: str, notes: str | None = None):
    row, _ = _project(project_id)
    return run_service.start_run(project_id, name, row["path"], notes=notes)


@router.post("/runs/{run_id}/finish")
def finish_run(project_id: str, run_id: str, status: str = "finished"):
    _project(project_id)
    return run_service.finish_run(run_id, status, project_id=project_id)


@router.get("/resources")
def resources(project_id: str):
    row, _ = _project(project_id)
    return resource_service.project_resources(row["path"])


@router.get("/images/check")
def image_checks(project_id: str):
    row, config = _project(project_id)
    return image_service.byoc_checks(row["path"], config.runtime.dockerfile)


@router.get("/images/catalog")
def image_catalog(project_id: str):
    _project(project_id)
    return image_service.catalog()


@router.get("/doctor")
def project_doctor(project_id: str):
    try:
        report = doctor_service.project_doctor(project_id)
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/profile")
def project_profile(project_id: str):
    row, config = _project(project_id)
    from capsulelab.services import profile_service

    return profile_service.get_profile(config.mode)


@router.post("/graph/index")
def index_project_graph(project_id: str):
    row, _ = _project(project_id)
    g = graph_service.index_project(project_id, row["path"])
    return graph_service.to_dict(g)


@router.get("/graph")
def get_project_graph(project_id: str):
    row, _ = _project(project_id)
    g = graph_service.get_graph(project_id)
    if not g.nodes:
        g = graph_service.index_project(project_id, row["path"])
    return graph_service.to_dict(g)


@router.get("/graph/search")
def search_project_graph(project_id: str, q: str = "", kind: str | None = None, limit: int = 25):
    row, _ = _project(project_id)
    return graph_service.search(project_id, row["path"], query=q, kind=kind, limit=limit)


@router.get("/graph/nodes/{node_id:path}")
def inspect_project_graph_node(project_id: str, node_id: str, depth: int = 1):
    row, _ = _project(project_id)
    try:
        return graph_service.inspect_node(project_id, row["path"], node_id, depth=depth)
    except KeyError:
        raise HTTPException(404, "Graph node not found")


@router.get("/graph/summary")
def project_graph_summary(project_id: str):
    row, _ = _project(project_id)
    return graph_service.summary(project_id, row["path"])


@router.post("/agent/context")
def build_agent_context(project_id: str):
    _project(project_id)
    ctx = agent_service.build_project_context(project_id)
    return _agent_context_response(ctx)


@router.get("/agent/context")
def get_agent_context(project_id: str):
    _project(project_id)
    ctx = agent_service.get_context(project_id)
    if not ctx:
        ctx = agent_service.build_project_context(project_id)
    return _agent_context_response(ctx)


@router.get("/agent/catalog")
def agent_catalog(project_id: str):
    return agent_service.catalog_contexts()


def _agent_context_response(ctx):
    return {
        "project_id": ctx.project_id,
        "project_name": ctx.project_name,
        "project_path": ctx.project_path,
        "summary": ctx.summary,
        "architecture": ctx.architecture,
        "setup_steps": ctx.setup_steps,
        "app_list": ctx.app_list,
        "data_mounts": ctx.data_mounts,
        "secret_refs": ctx.secret_refs,
        "graph_summary": ctx.graph_summary,
        "known_issues": ctx.known_issues,
        "check_count": len(ctx.check_results),
        "recent_runs": ctx.recent_runs,
    }


@router.get("/agent/actions")
def list_agent_actions(project_id: str):
    _project(project_id)
    return [asdict(action) for action in agent_service.list_actions(project_id)]


@router.post("/agent/actions")
def propose_agent_action(project_id: str, req: AgentActionRequest):
    _project(project_id)
    try:
        return asdict(agent_service.propose_action(project_id, req.action_type, req.title, req.rationale, req.files))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/agent/actions/{action_id}/review")
def review_agent_action(project_id: str, action_id: str, req: AgentActionReviewRequest):
    _project(project_id)
    try:
        return asdict(agent_service.review_action(project_id, action_id, req.approved, req.reviewer, req.note))
    except ValueError as e:
        raise HTTPException(404, str(e))
