import json
import asyncio

from fastapi import HTTPException

from backend.api import apps
from starlette.requests import Request


def test_resolve_share_endpoint_returns_share(monkeypatch):
    monkeypatch.setattr(apps.projects, "get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})

    def fake_resolve(token, session_id=None, bind_session=True):
        return {
            "token": token,
            "project_id": "cap-demo",
            "app_id": "jupyter",
            "target_url": "http://localhost:10000/projects/cap-demo/apps/jupyter/",
            "session_id": session_id,
        }

    monkeypatch.setattr(apps.app_service, "resolve_share_url", fake_resolve)

    result = apps.resolve_app_share("cap-demo", "token-1", apps.ResolveShareRequest(session_id="browser-1"))

    assert result["target_url"].endswith("/projects/cap-demo/apps/jupyter/")
    assert result["session_id"] == "browser-1"


def test_resolve_share_endpoint_rejects_invalid_share(monkeypatch):
    monkeypatch.setattr(apps.projects, "get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})

    def fake_resolve(*args, **kwargs):
        raise apps.app_service.ShareAccessError("expired")

    monkeypatch.setattr(apps.app_service, "resolve_share_url", fake_resolve)

    try:
        apps.resolve_app_share("cap-demo", "token-1", apps.ResolveShareRequest())
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Expected HTTPException")


def test_cleanup_shares_endpoint_returns_revoked_count(monkeypatch):
    monkeypatch.setattr(apps.projects, "get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})
    monkeypatch.setattr(apps.app_service, "cleanup_expired_share_urls", lambda: 3)

    assert apps.cleanup_app_shares("cap-demo") == {"revoked": 3}


def test_proxy_app_request_forwards_to_local_port(monkeypatch):
    received = {}

    class FakeResponse:
        status = 200

        def read(self):
            return json.dumps({"ok": True, "path": received["path"]}).encode("utf-8")

        def getheaders(self):
            return [("Content-Type", "application/json")]

    class FakeConnection:
        def __init__(self, host, port, timeout=15):
            received["host"] = host
            received["port"] = port
            received["timeout"] = timeout

        def request(self, method, path, body=None, headers=None):
            received["method"] = method
            received["path"] = path
            received["body"] = body
            received["headers"] = headers or {}

        def getresponse(self):
            return FakeResponse()

        def close(self):
            received["closed"] = True

    monkeypatch.setattr(apps.http.client, "HTTPConnection", FakeConnection)
    monkeypatch.setattr(apps.projects, "get", lambda project_id: {"id": project_id, "name": "demo", "path": "/tmp/demo"})

    class FakeConfig:
        name = "demo"
        apps = [type("AppCfg", (), {"id": "jupyter", "name": "Jupyter", "command": "jupyter lab", "port": 8123, "url_path": "/", "kind": "web"})()]

    monkeypatch.setattr(apps.project_service, "load_config", lambda path: FakeConfig())
    monkeypatch.setattr(apps.project_service, "get_container_name", lambda name: "cap-demo")
    monkeypatch.setattr(apps.app_service, "get_app_status", lambda *args, **kwargs: {"container_running": True})
    monkeypatch.setattr(apps.app_service, "get_app_config", lambda config, app_id: config.apps[0])

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/projects/cap-demo/apps/jupyter/proxy/hello",
        "raw_path": b"/api/projects/cap-demo/apps/jupyter/proxy/hello",
        "query_string": b"x=1",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "http_version": "1.1",
    }
    request = Request(scope, receive)
    response = asyncio.run(apps.proxy_app_request("cap-demo", "jupyter", "hello", request))

    assert response.status_code == 200
    assert json.loads(response.body.decode("utf-8")) == {"ok": True, "path": "/hello?x=1"}
    assert received["host"] == "127.0.0.1"
    assert received["port"] == 8123
    assert received["path"] == "/hello?x=1"
    assert "host" not in received["headers"]
    assert received["closed"] is True
