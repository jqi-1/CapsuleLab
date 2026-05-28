import shlex
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from capsulelab.core.errors import CapsuleLabError, ErrorCode, Severity
from capsulelab.core.project import AppConfig
from capsulelab.db.repositories import apps, shares
from capsulelab.services.runtime_service import RuntimeAdapter


class AppError(CapsuleLabError):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(ErrorCode.APP_NOT_FOUND, message, severity=Severity.ERROR, detail=detail)


class ShareAccessError(AppError):
    pass


def app_log_path(app_id: str) -> str:
    return f"/tmp/cap-{app_id}.log"


def check_alive(adapter: RuntimeAdapter, container_name: str, pid: int) -> bool:
    try:
        result = adapter.exec_run(
            container_name,
            f"kill -0 {pid} 2>/dev/null && echo alive || echo dead",
        )
        return result.strip() == "alive"
    except Exception:
        return False


def check_port_available(adapter: RuntimeAdapter, port: int) -> tuple[bool, str]:
    import socket

    used = adapter.get_used_ports()
    if port in used:
        return False, f"Port {port} is already in use on the host (Docker)."
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", port))
        s.close()
        return True, ""
    except OSError:
        return False, f"Port {port} is already in use on the host."


def get_app_url(app_cfg: AppConfig) -> str:
    if app_cfg.port is None:
        return ""
    return f"http://localhost:{app_cfg.port}{app_cfg.url_path}"


def get_proxy_app_url(project_id: str, app_cfg: AppConfig, proxy_base_url: str = "http://localhost:10000") -> str:
    if app_cfg.port is None:
        return ""
    base = proxy_base_url.rstrip("/")
    path = app_cfg.url_path if app_cfg.url_path.startswith("/") else f"/{app_cfg.url_path}"
    return f"{base}/projects/{project_id}/apps/{app_cfg.id}{path}"


def create_share_url(
    project_id: str,
    app_cfg: AppConfig,
    public_base_url: str = "http://localhost:10000",
    hours: int = 48,
) -> dict:
    if app_cfg.port is None:
        raise AppError(f"App '{app_cfg.id}' is not a web app and cannot be shared.")
    if hours < 1 or hours > 168:
        raise AppError("Share duration must be between 1 and 168 hours.")
    token = token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
    url = f"{public_base_url.rstrip('/')}/share/{token}"
    shares.create(token, project_id, app_cfg.id, url, expires_at.isoformat())
    return {
        "token": token,
        "project_id": project_id,
        "app_id": app_cfg.id,
        "url": url,
        "target_url": get_proxy_app_url(project_id, app_cfg, public_base_url),
        "expires_at": expires_at.isoformat(),
        "hours": hours,
    }


def list_share_urls(project_id: str, app_id: str | None = None) -> list[dict]:
    now = datetime.now(timezone.utc)
    results = []
    for share in shares.list(project_id, app_id=app_id):
        expires_at = _parse_datetime(share["expires_at"])
        share["expired"] = expires_at <= now if expires_at else True
        results.append(share)
    return results


def resolve_share_url(token: str, session_id: str | None = None, bind_session: bool = True) -> dict:
    share = shares.get(token)
    if not share or share.get("revoked_at"):
        raise ShareAccessError("Share link not found or revoked.")
    expires_at = _parse_datetime(share["expires_at"])
    if not expires_at or expires_at <= datetime.now(timezone.utc):
        shares.revoke(token)
        raise ShareAccessError("Share link has expired.")
    stored_session = share.get("session_id")
    if stored_session and session_id and stored_session != session_id:
        raise ShareAccessError("Share link is bound to a different browser session.")
    if bind_session and session_id and not stored_session:
        shares.bind_session(token, session_id)
        share["session_id"] = session_id
    else:
        shares.touch(token)
    share["expired"] = False
    share["target_url"] = _share_target_url(share)
    return share


def cleanup_expired_share_urls() -> int:
    return shares.revoke_expired(datetime.now(timezone.utc).isoformat())


def revoke_share_url(token: str) -> bool:
    return shares.revoke(token)


def _share_target_url(share: dict) -> str:
    row = None
    try:
        from capsulelab.db.repositories import projects

        row = projects.get(share["project_id"])
    except Exception:
        row = None
    if not row:
        return ""
    try:
        from capsulelab.services import project_service

        config = project_service.load_config(row["path"])
        app_cfg = get_app_config(config, share["app_id"])
    except Exception:
        return ""
    base = share["url"].split("/share/", 1)[0]
    return get_proxy_app_url(share["project_id"], app_cfg, base)


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def build_start_command(app_cfg: AppConfig, log_file: str) -> str:
    return f"nohup {app_cfg.command} > {log_file} 2>&1 & echo $!"


def start_app(adapter: RuntimeAdapter, project_id: str, app_cfg: AppConfig, container_name: str) -> dict:
    if not adapter.is_running(container_name):
        raise AppError(f"Container '{container_name}' is not running. Start the project first.")

    state = apps.get_state(project_id, app_cfg.id)
    pid = state.get("pid") if state else None
    if state and state["status"] == "running" and pid:
        if check_alive(adapter, container_name, pid):
            return {
                "status": "already_running",
                "app": app_cfg.id,
                "pid": pid,
                "url": get_app_url(app_cfg),
                "proxy_url": get_proxy_app_url(project_id, app_cfg),
            }

    if app_cfg.port is not None:
        ok, msg = check_port_available(adapter, app_cfg.port)
        if not ok:
            raise AppError(msg)

    log_file = app_log_path(app_cfg.id)
    cmd = build_start_command(app_cfg, log_file)
    try:
        output = adapter.exec_run(container_name, cmd, detach=False)
        pid = int(output.strip())
    except Exception as e:
        apps.set_state(project_id, app_cfg.id, "failed", port=app_cfg.port)
        raise AppError(f"Failed to start app: {e}") from e

    apps.set_state(project_id, app_cfg.id, "running", pid=pid, port=app_cfg.port)

    alive = check_alive(adapter, container_name, pid)
    if not alive:
        apps.set_state(project_id, app_cfg.id, "failed", pid=pid, port=app_cfg.port)
        raise AppError(f"App started but process is not alive. Check logs: cap app logs {app_cfg.id}")

    return {
        "status": "started",
        "app": app_cfg.id,
        "pid": pid,
        "url": get_app_url(app_cfg),
        "proxy_url": get_proxy_app_url(project_id, app_cfg),
    }


def stop_app(adapter: RuntimeAdapter, project_id: str, app_cfg: AppConfig, container_name: str) -> dict:
    if not adapter.is_running(container_name):
        apps.set_state(project_id, app_cfg.id, "stopped")
        return {"status": "stopped", "app": app_cfg.id}

    state = apps.get_state(project_id, app_cfg.id)
    pid = state.get("pid") if state else None

    if pid:
        if check_alive(adapter, container_name, pid):
            adapter.exec_run(container_name, f"kill {pid} 2>/dev/null || true")
    if not app_cfg.command.strip():
        apps.set_state(project_id, app_cfg.id, "stopped")
        return {"status": "stopped", "app": app_cfg.id}
    first_word = app_cfg.command.split()[0]
    adapter.exec_run(container_name, f"pkill -f {shlex.quote(first_word)} 2>/dev/null || true")
    apps.set_state(project_id, app_cfg.id, "stopped")

    return {"status": "stopped", "app": app_cfg.id}


def get_app_status(adapter: RuntimeAdapter, project_id: str, app_cfg: AppConfig, container_name: str) -> dict:
    try:
        running = adapter.is_running(container_name)
    except Exception:
        running = False
    state = apps.get_state(project_id, app_cfg.id)
    alive = None
    state_status = state.get("status") if state else "stopped"
    if running and state and state.get("pid"):
        alive = check_alive(adapter, container_name, state["pid"])
        if alive is False and state_status == "running":
            apps.set_state(project_id, app_cfg.id, "failed", pid=state["pid"], port=state.get("port"))
            state_status = "failed"
    return {
        "app_id": app_cfg.id,
        "name": app_cfg.name,
        "port": app_cfg.port,
        "url": get_app_url(app_cfg),
        "proxy_url": get_proxy_app_url(project_id, app_cfg),
        "url_path": app_cfg.url_path,
        "kind": app_cfg.kind,
        "log_path": app_log_path(app_cfg.id),
        "container_running": running,
        "state": state_status,
        "pid": state.get("pid") if state else None,
        "alive": alive if running else None,
    }


def get_app_logs(adapter: RuntimeAdapter, container_name: str, app_id: str, tail: int = 50) -> str:
    if not adapter.is_running(container_name):
        raise AppError(f"Container '{container_name}' is not running.")
    log_file = app_log_path(app_id)
    cmd = f"tail -n {tail} {log_file} 2>&1 || echo 'No app log file found'"
    return adapter.exec_run(container_name, cmd)


def get_app_config(config, app_id: str) -> AppConfig:
    app_cfg = next((a for a in config.apps if a.id == app_id), None)
    if not app_cfg:
        raise AppError(f"App '{app_id}' not found in project config.")
    return app_cfg
