from backend.services import ssh_service
from backend.db import sqlite


def test_remote_project_path_default_root():
    loc = {"user": "alice", "project_root": None}

    assert ssh_service.remote_project_path("/home/me/demo", loc) == "/home/alice/capsulelab-projects/demo"


def test_remote_project_path_custom_root():
    loc = {"user": "alice", "project_root": "/srv/projects"}

    assert ssh_service.remote_project_path("/home/me/demo", loc) == "/srv/projects/demo"


def test_check_status_remote_path_missing(monkeypatch):
    def fake_run(host, command, user=None, timeout=60):
        if command == "echo reachable":
            return "reachable"
        if command.startswith("docker info"):
            return "27.0"
        if command.startswith("nvidia-smi"):
            raise ssh_service.SSHError("missing")
        if "test -d" in command:
            return "missing"
        raise AssertionError(command)

    monkeypatch.setattr(ssh_service, "_run_ssh", fake_run)

    status = ssh_service.check_status("example.test", remote_path="/tmp/demo")

    assert status.reachable is True
    assert status.docker_available is True
    assert status.project_path_exists is False


def test_remote_build_quotes_paths(monkeypatch):
    calls = []

    def fake_run(host, command, user=None, timeout=60):
        calls.append(command)
        return "ok"

    monkeypatch.setattr(ssh_service, "_run_ssh", fake_run)

    ssh_service.build("example.test", "/tmp/project with spaces", "Dockerfile", "demo", "dev")

    assert "'/tmp/project with spaces/Dockerfile'" in calls[0]
    assert "'/tmp/project with spaces'" in calls[0]


def test_remote_run_quotes_volume_path(monkeypatch):
    calls = []

    def fake_run(host, command, user=None, timeout=60):
        calls.append(command)
        return "ok"

    monkeypatch.setattr(ssh_service, "_run_ssh", fake_run)

    ssh_service.run("example.test", "cap-demo", "demo:dev", "/tmp/project with spaces", False)

    assert "'/tmp/project with spaces:/workspace'" in calls[0]


def test_assign_tunnel_ports_persists_workbench_style_pairs(monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite, "DB_DIR", tmp_path)
    monkeypatch.setattr(sqlite, "DB_PATH", tmp_path / "capsulelab.db")
    sqlite.init_db()
    sqlite.register_location("loc-one", "one", "ssh", "one.example", "alice", None, "docker", False)
    sqlite.register_location("loc-two", "two", "ssh", "two.example", "bob", None, "docker", False)

    first = ssh_service.assign_tunnel_ports("loc-one")
    second = ssh_service.assign_tunnel_ports("loc-two")
    again = ssh_service.assign_tunnel_ports("loc-one")

    assert first.proxy_port == 10000
    assert first.service_port == 10001
    assert second.proxy_port == 10002
    assert second.service_port == 10003
    assert again.proxy_port == first.proxy_port


def test_tunnel_command_uses_two_local_forwards():
    loc = {"id": "loc-one", "name": "one", "host": "example.test", "user": "alice"}
    spec = ssh_service.TunnelSpec(proxy_port=10004, service_port=10005)

    command = ssh_service.tunnel_command(loc, spec)

    assert command == [
        "ssh",
        "-N",
        "-L",
        "10004:localhost:10000",
        "-L",
        "10005:localhost:10001",
        "alice@example.test",
    ]


def test_tunnel_info_returns_urls_and_shell_safe_command(monkeypatch):
    loc = {"id": "loc-one", "name": "one", "host": "example.test", "user": "alice"}

    monkeypatch.setattr(ssh_service, "assign_tunnel_ports", lambda location_id: ssh_service.TunnelSpec(10000, 10001))

    info = ssh_service.tunnel_info(loc)

    assert info["proxy_url"] == "http://localhost:10000"
    assert info["service_url"] == "http://localhost:10001"
    assert "10000:localhost:10000" in info["command_text"]
