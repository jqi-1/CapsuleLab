from fastapi import APIRouter, HTTPException, Query

from capsulelab.db.repositories import projects
from capsulelab.services import app_service, docker_service, project_service
from capsulelab.services.runtime_service import LocalDockerAdapter

router = APIRouter()


def get_project_logs(
    project_id: str,
    tail: int = Query(100, ge=0),
):
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    if not docker_service.container_exists(container_name):
        raise HTTPException(404, "Container not found")
    try:
        output = docker_service.logs(container_name, tail=tail)
        return {"logs": output}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/apps/{app_id}/logs")
def get_app_logs(
    project_id: str,
    app_id: str,
    tail: int = Query(50, ge=0),
):
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    try:
        app_cfg = app_service.get_app_config(config, app_id)
    except app_service.AppError as e:
        raise HTTPException(404, str(e))
    try:
        output = app_service.get_app_logs(LocalDockerAdapter(), container_name, app_cfg.id, tail=tail)
        return {"logs": output, "app_id": app_cfg.id}
    except app_service.AppError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
