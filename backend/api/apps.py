from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services import project_service, app_service
from backend.db.sqlite import get_project

router = APIRouter()


class ShareAppRequest(BaseModel):
    public_base_url: str = "http://localhost:10000"
    hours: int = 48


@router.post("/{app_id}/start")
def start_app(project_id: str, app_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    try:
        app_cfg = app_service.get_app_config(config, app_id)
    except app_service.AppError as e:
        raise HTTPException(404, str(e))
    try:
        result = app_service.start_app(project_id, app_cfg, container_name)
        return result
    except app_service.AppError as e:
        raise HTTPException(500, str(e))


@router.post("/{app_id}/stop")
def stop_app(project_id: str, app_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    try:
        app_cfg = app_service.get_app_config(config, app_id)
    except app_service.AppError as e:
        raise HTTPException(404, str(e))
    try:
        result = app_service.stop_app(project_id, app_cfg, container_name)
        return result
    except app_service.AppError as e:
        raise HTTPException(500, str(e))


@router.get("/{app_id}/status")
def app_status(project_id: str, app_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    try:
        app_cfg = app_service.get_app_config(config, app_id)
    except app_service.AppError as e:
        raise HTTPException(404, str(e))
    return app_service.get_app_status(project_id, app_cfg, container_name)


@router.post("/{app_id}/share")
def share_app(project_id: str, app_id: str, req: ShareAppRequest):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    try:
        app_cfg = app_service.get_app_config(config, app_id)
        return app_service.create_share_url(project_id, app_cfg, req.public_base_url, req.hours)
    except app_service.AppError as e:
        raise HTTPException(400, str(e))


@router.get("/{app_id}/shares")
def app_shares(project_id: str, app_id: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return app_service.list_share_urls(project_id, app_id=app_id)


@router.delete("/shares/{token}")
def revoke_app_share(project_id: str, token: str):
    row = get_project(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    if not app_service.revoke_share_url(token):
        raise HTTPException(404, "Share not found")
    return {"status": "revoked", "token": token}
