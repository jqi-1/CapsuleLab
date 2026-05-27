import pytest
from capsulelab.services import docker_service
from capsulelab.services.app_service import (
    check_alive, check_port_available,
    get_app_url, get_proxy_app_url, create_share_url, list_share_urls,
    resolve_share_url, cleanup_expired_share_urls, revoke_share_url,
    build_start_command, get_app_config, get_app_status, AppError, ShareAccessError,
)
from capsulelab.db import sqlite
from capsulelab.db.repositories import projects
from capsulelab.core.project import AppConfig


def test_app_log_path():
    path = docker_service.app_log_path("jupyter")
    assert path == "/tmp/cap-jupyter.log"


def test_app_log_path_special_chars():
    path = docker_service.app_log_path("my-app_123")
    assert path == "/tmp/cap-my-app_123.log"


def test_get_app_url():
    cfg = AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)
    assert get_app_url(cfg) == "http://localhost:8888/"


def test_get_app_url_custom_path():
    cfg = AppConfig(name="Streamlit", id="streamlit", command="streamlit run app.py", port=8501, url_path="/app")
    assert get_app_url(cfg) == "http://localhost:8501/app"


def test_get_proxy_app_url():
    cfg = AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)

    assert get_proxy_app_url("cap-demo", cfg) == "http://localhost:10000/projects/cap-demo/apps/jupyter/"


def test_get_proxy_app_url_custom_base_and_path():
    cfg = AppConfig(name="Streamlit", id="streamlit", command="streamlit", port=8501, url_path="/app")

    assert get_proxy_app_url("cap-demo", cfg, "https://share.example/") == "https://share.example/projects/cap-demo/apps/streamlit/app"


def test_build_start_command():
    cfg = AppConfig(name="Jupyter", id="jupyter", command="jupyter lab --port=8888", port=8888)
    cmd = build_start_command(cfg, "/tmp/cap-jupyter.log")
    assert "nohup" in cmd
    assert "jupyter lab --port=8888" in cmd
    assert "/tmp/cap-jupyter.log" in cmd


def test_get_app_config_found():
    apps = [
        AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888),
        AppConfig(name="Streamlit", id="streamlit", command="streamlit run app.py", port=8501),
    ]

    config = type("FakeConfig", (), {"apps": apps})()

    result = get_app_config(config, "jupyter")
    assert result.id == "jupyter"


def test_get_app_config_not_found():
    apps = [AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)]

    config = type("FakeConfig", (), {"apps": apps})()

    with pytest.raises(AppError, match="not found"):
        get_app_config(config, "missing")


def test_get_app_status_includes_runtime_metadata(monkeypatch):
    cfg = AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)

    monkeypatch.setattr("capsulelab.services.app_service.docker_service.is_running", lambda _: False)
    monkeypatch.setattr("capsulelab.db.repositories.apps.get_state", lambda *_: None)

    status = get_app_status("cap-demo", cfg, "cap-demo")

    assert status["app_id"] == "jupyter"
    assert status["url"] == "http://localhost:8888/"
    assert status["proxy_url"] == "http://localhost:10000/projects/cap-demo/apps/jupyter/"
    assert status["log_path"] == "/tmp/cap-jupyter.log"
    assert status["state"] == "stopped"
    assert status["alive"] is None


def test_create_list_and_revoke_share_url(monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path)
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "capsulelab.db")
    sqlite.init_db()
    projects.register("cap-demo", "demo", str(tmp_path))
    cfg = AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)

    share = create_share_url("cap-demo", cfg, public_base_url="https://example.test", hours=2)
    shares = list_share_urls("cap-demo", "jupyter")

    assert share["url"].startswith("https://example.test/share/")
    assert share["target_url"] == "https://example.test/projects/cap-demo/apps/jupyter/"
    assert shares[0]["token"] == share["token"]
    assert shares[0]["expired"] is False
    assert revoke_share_url(share["token"]) is True
    assert list_share_urls("cap-demo", "jupyter") == []


def test_resolve_share_url_binds_session_and_rejects_other_session(monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path)
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "capsulelab.db")
    sqlite.init_db()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".workbench").mkdir()
    (project / ".workbench" / "project.yaml").write_text(
        "name: demo\n"
        "runtime:\n"
        "  image: demo:dev\n"
        "apps:\n"
        "  - name: Jupyter\n"
        "    id: jupyter\n"
        "    command: jupyter lab\n"
        "    port: 8888\n"
    )
    projects.register("cap-demo", "demo", str(project))
    cfg = AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)
    share = create_share_url("cap-demo", cfg, public_base_url="https://example.test", hours=2)

    resolved = resolve_share_url(share["token"], session_id="browser-1")

    assert resolved["session_id"] == "browser-1"
    assert resolved["target_url"] == "https://example.test/projects/cap-demo/apps/jupyter/"
    with pytest.raises(ShareAccessError, match="different browser session"):
        resolve_share_url(share["token"], session_id="browser-2")


def test_cleanup_expired_share_urls(monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path)
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "capsulelab.db")
    sqlite.init_db()
    projects.register("cap-demo", "demo", str(tmp_path))
    cfg = AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)
    share = create_share_url("cap-demo", cfg, hours=1)
    from capsulelab.db.repositories import shares
    with sqlite.get_db() as conn:
        conn.execute("UPDATE app_shares SET expires_at = '2000-01-01T00:00:00+00:00' WHERE token = ?", (share["token"],))

    assert cleanup_expired_share_urls() == 1
    assert list_share_urls("cap-demo", "jupyter") == []


def test_create_share_url_rejects_process_app():
    cfg = AppConfig(name="Worker", id="worker", command="python worker.py", kind="process")

    with pytest.raises(AppError, match="cannot be shared"):
        create_share_url("cap-demo", cfg)


def test_get_app_status_marks_stale_running_state_failed(monkeypatch):
    cfg = AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)
    updates = []

    monkeypatch.setattr("capsulelab.services.app_service.docker_service.is_running", lambda _: True)
    monkeypatch.setattr(
        "capsulelab.db.repositories.apps.get_state",
        lambda *_: {"status": "running", "pid": 123, "port": 8888},
    )
    monkeypatch.setattr("capsulelab.services.app_service.check_alive", lambda *_: False)
    monkeypatch.setattr(
        "capsulelab.db.repositories.apps.set_state",
        lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    status = get_app_status("cap-demo", cfg, "cap-demo")

    assert status["state"] == "failed"
    assert status["alive"] is False
    assert updates[0][0] == ("cap-demo", "jupyter", "failed")


def test_check_alive_not_running():
    assert check_alive("nonexistent-container-xyz", 12345) is False


@pytest.mark.docker
def test_check_port_available():
    ok, msg = check_port_available(1)
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
