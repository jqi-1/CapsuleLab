from fastapi import HTTPException

from backend.api import locations


def test_location_tunnel_endpoint_returns_tunnel(monkeypatch):
    loc = {"id": "loc-demo", "name": "demo", "host": "example.test", "user": "alice"}
    monkeypatch.setattr("capsulelab.db.repositories.locations.get_by_name", lambda name: loc)
    monkeypatch.setattr(
        locations.ssh_service,
        "tunnel_info",
        lambda location: {"location": location["name"], "proxy_url": "http://localhost:10000"},
    )

    result = locations.location_tunnel("demo")

    assert result == {"location": "demo", "proxy_url": "http://localhost:10000"}


def test_location_tunnel_endpoint_404s_for_missing_location(monkeypatch):
    monkeypatch.setattr("capsulelab.db.repositories.locations.get_by_name", lambda name: None)

    try:
        locations.location_tunnel("missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")


def test_location_status_reports_project_root_and_disk(monkeypatch):
    loc = {
        "id": "loc-demo",
        "name": "demo",
        "host": "example.test",
        "user": "alice",
        "project_root": "/srv/capsules",
        "gpu": 0,
    }
    monkeypatch.setattr("capsulelab.db.repositories.locations.get_by_name", lambda name: loc)
    monkeypatch.setattr(
        locations.ssh_service,
        "check_status",
        lambda host, user, remote_path=None: type("RemoteStatus", (), {
            "reachable": True,
            "docker_available": True,
            "docker_version": "27.0",
            "gpu_available": False,
            "gpu_name": "",
            "project_path_exists": True,
            "disk_total_gb": 100.0,
            "disk_free_gb": 75.0,
            "disk_used_percent": 25,
            "error": "",
        })(),
    )
    monkeypatch.setattr(locations.ssh_service, "tunnel_info", lambda location: {"location": location["name"]})

    result = locations.location_status("demo")

    assert result["project_root"] == "/srv/capsules"
    assert result["project_root_exists"] is True
    assert result["disk_total_gb"] == 100.0
    assert result["disk_free_gb"] == 75.0
    assert result["disk_used_percent"] == 25
