import http.client

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from capsulelab.db.repositories import projects
from capsulelab.services import app_service, project_service
from capsulelab.services.runtime_service import LocalDockerAdapter

router = APIRouter()


class ShareAppRequest(BaseModel):
    public_base_url: str = "http://localhost:10000"
    hours: int = 48


class ResolveShareRequest(BaseModel):
    session_id: str | None = None
    bind_session: bool = True


@router.post("/{app_id}/start")
def start_app(project_id: str, app_id: str):
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
        result = app_service.start_app(LocalDockerAdapter(), project_id, app_cfg, container_name)
        return result
    except app_service.AppError as e:
        raise HTTPException(500, str(e))


@router.post("/{app_id}/stop")
def stop_app(project_id: str, app_id: str):
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
        result = app_service.stop_app(LocalDockerAdapter(), project_id, app_cfg, container_name)
        return result
    except app_service.AppError as e:
        raise HTTPException(500, str(e))


@router.get("/{app_id}/status")
def app_status(project_id: str, app_id: str):
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    container_name = project_service.get_container_name(config.name)
    try:
        app_cfg = app_service.get_app_config(config, app_id)
    except app_service.AppError as e:
        raise HTTPException(404, str(e))
    return app_service.get_app_status(LocalDockerAdapter(), project_id, app_cfg, container_name)


@router.post("/{app_id}/share")
def share_app(project_id: str, app_id: str, req: ShareAppRequest):
    row = projects.get(project_id)
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
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return app_service.list_share_urls(project_id, app_id=app_id)


@router.delete("/shares/{token}")
def revoke_app_share(project_id: str, token: str):
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    if not app_service.revoke_share_url(token):
        raise HTTPException(404, "Share not found")
    return {"status": "revoked", "token": token}


@router.post("/shares/{token}/resolve")
def resolve_app_share(project_id: str, token: str, req: ResolveShareRequest):
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    try:
        share = app_service.resolve_share_url(token, session_id=req.session_id, bind_session=req.bind_session)
    except app_service.ShareAccessError as e:
        raise HTTPException(403, str(e))
    if share["project_id"] != project_id:
        raise HTTPException(404, "Share not found")
    return share


@router.post("/shares/cleanup")
def cleanup_app_shares(project_id: str):
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return {"revoked": app_service.cleanup_expired_share_urls()}


@router.api_route("/{app_id}/proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def proxy_app_request(project_id: str, app_id: str, path: str, request: Request):
    row = projects.get(project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    config = project_service.load_config(row["path"])
    try:
        app_cfg = app_service.get_app_config(config, app_id)
    except app_service.AppError as e:
        raise HTTPException(404, str(e))
    if app_cfg.port is None:
        raise HTTPException(400, f"App '{app_id}' does not expose a port and cannot be proxied.")

    status = app_service.get_app_status(
        LocalDockerAdapter(), project_id, app_cfg, project_service.get_container_name(config.name)
    )
    if not status["container_running"]:
        raise HTTPException(409, f"Container '{project_service.get_container_name(config.name)}' is not running.")

    conn = http.client.HTTPConnection("127.0.0.1", app_cfg.port, timeout=15)
    query = f"?{request.url.query}" if request.url.query else ""
    headers = {key: value for key, value in request.headers.items() if key.lower() not in {"host", "content-length"}}
    body = await request.body()
    try:
        conn.request(request.method, f"/{path}{query}", body=body if body else None, headers=headers)
        upstream = conn.getresponse()
        payload = upstream.read()
        response_headers = {
            key: value
            for key, value in upstream.getheaders()
            if key.lower()
            not in {
                "transfer-encoding",
                "connection",
                "keep-alive",
                "proxy-authenticate",
                "proxy-authorization",
                "te",
                "trailers",
                "upgrade",
            }
        }
        return Response(
            content=payload,
            status_code=upstream.status,
            media_type=response_headers.get("content-type"),
            headers=response_headers,
        )
    except Exception as e:
        raise HTTPException(502, f"Proxy request failed: {e}")
    finally:
        conn.close()
