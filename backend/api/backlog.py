from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.sqlite import get_project
from backend.models.project import ProjectConfig
from backend.services import (
    git_service,
    image_service,
    resource_service,
    run_service,
    secrets_service,
    project_service,
    doctor_service,
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


def _project(project_id: str) -> tuple[dict, ProjectConfig]:
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row, project_service.load_config(row["path"])


@router.get("/git/status")
def git_status(project_id: str):
    row, _ = _project(project_id)
    return git_service.git_status(row["path"])


@router.get("/git/history")
def git_history(project_id: str, limit: int = 10):
    row, _ = _project(project_id)
    try:
        return git_service.history(row["path"], limit=limit)
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())


@router.get("/git/branches")
def git_branches(project_id: str):
    row, _ = _project(project_id)
    try:
        return git_service.branches(row["path"])
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())


@router.post("/git/branches")
def git_switch_branch(project_id: str, req: GitBranchRequest):
    row, _ = _project(project_id)
    try:
        return git_service.switch_branch(row["path"], req.branch, create=req.create)
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())


@router.post("/git/commit")
def git_commit(project_id: str, req: GitCommitRequest):
    row, _ = _project(project_id)
    try:
        return git_service.commit(row["path"], req.message, all_changes=req.all_changes)
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())


@router.post("/git/fetch")
def git_fetch(project_id: str, req: GitRemoteRequest):
    row, _ = _project(project_id)
    try:
        return git_service.fetch(row["path"], remote=req.remote)
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())


@router.post("/git/pull")
def git_pull(project_id: str, req: GitRemoteRequest):
    row, _ = _project(project_id)
    try:
        return git_service.pull(row["path"], remote=req.remote, branch=req.branch)
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())


@router.post("/git/push")
def git_push(project_id: str, req: GitPushRequest):
    row, _ = _project(project_id)
    try:
        return git_service.push(row["path"], remote=req.remote, branch=req.branch, set_upstream=req.set_upstream)
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())


@router.post("/git/publish")
def git_publish(project_id: str, req: GitPublishRequest):
    row, _ = _project(project_id)
    try:
        return git_service.publish(row["path"], req.remote_url, remote=req.remote, branch=req.branch)
    except git_service.GitError as e:
        raise HTTPException(400, e.to_dict())


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
    from backend.services import profile_service
    return profile_service.get_profile(config.mode)


@router.post("/graph/index")
def index_project_graph(project_id: str):
    row, _ = _project(project_id)
    from backend.services import graph_service
    g = graph_service.index_project(project_id, row["path"])
    return {"node_count": len(g.nodes), "edge_count": len(g.edges)}


@router.get("/graph")
def get_project_graph(project_id: str):
    row, _ = _project(project_id)
    from backend.services import graph_service
    g = graph_service.get_graph(project_id)
    if not g.nodes:
        g = graph_service.index_project(project_id, row["path"])
    return {"project_id": g.project_id, "nodes": len(g.nodes), "edges": len(g.edges)}


@router.get("/graph/summary")
def project_graph_summary(project_id: str):
    row, _ = _project(project_id)
    from backend.services import graph_service
    return graph_service.summary(project_id, row["path"])


@router.post("/agent/context")
def build_agent_context(project_id: str):
    _project(project_id)
    from backend.services import agent_service
    ctx = agent_service.build_project_context(project_id)
    return {
        "project_id": ctx.project_id,
        "project_name": ctx.project_name,
        "architecture": ctx.architecture,
        "setup_steps": ctx.setup_steps,
        "app_list": ctx.app_list,
        "check_count": len(ctx.check_results),
        "recent_runs": ctx.recent_runs,
    }


@router.get("/agent/context")
def get_agent_context(project_id: str):
    _project(project_id)
    from backend.services import agent_service
    ctx = agent_service.get_context(project_id)
    if not ctx:
        ctx = agent_service.build_project_context(project_id)
    return {
        "project_id": ctx.project_id,
        "project_name": ctx.project_name,
        "architecture": ctx.architecture,
        "setup_steps": ctx.setup_steps,
        "app_list": ctx.app_list,
        "check_count": len(ctx.check_results),
        "recent_runs": ctx.recent_runs,
    }


@router.get("/agent/catalog")
def agent_catalog(project_id: str):
    from backend.services import agent_service
    return agent_service.catalog_contexts()
