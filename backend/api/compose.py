from fastapi import APIRouter, HTTPException, Query

from backend.db.sqlite import get_project
from backend.services import compose_service

router = APIRouter()


def _project_path(project_id: str) -> str:
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row["path"]


@router.get("/compose/status")
def compose_status(project_id: str):
    return compose_service.status(_project_path(project_id))


@router.post("/compose/up")
def compose_up(project_id: str, build: bool = Query(False), profiles: list[str] = Query(default=[])):
    try:
        return compose_service.up(_project_path(project_id), build=build, profiles=profiles)
    except compose_service.ComposeError as e:
        raise HTTPException(400, str(e))


@router.post("/compose/down")
def compose_down(project_id: str, volumes: bool = Query(False)):
    try:
        return compose_service.down(_project_path(project_id), volumes=volumes)
    except compose_service.ComposeError as e:
        raise HTTPException(400, str(e))


@router.get("/compose/logs")
def compose_logs(project_id: str, service: str | None = None, tail: int = Query(50, ge=0)):
    try:
        return {"logs": compose_service.logs(_project_path(project_id), service=service, tail=tail)}
    except compose_service.ComposeError as e:
        raise HTTPException(400, str(e))


@router.get("/compose/inspect")
def compose_inspect(project_id: str):
    return compose_service.status(_project_path(project_id))
