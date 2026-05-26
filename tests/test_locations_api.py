from fastapi import HTTPException

from backend.api import locations


def test_location_tunnel_endpoint_returns_tunnel(monkeypatch):
    loc = {"id": "loc-demo", "name": "demo", "host": "example.test", "user": "alice"}
    monkeypatch.setattr(locations, "get_location_by_name", lambda name: loc)
    monkeypatch.setattr(
        locations.ssh_service,
        "tunnel_info",
        lambda location: {"location": location["name"], "proxy_url": "http://localhost:10000"},
    )

    result = locations.location_tunnel("demo")

    assert result == {"location": "demo", "proxy_url": "http://localhost:10000"}


def test_location_tunnel_endpoint_404s_for_missing_location(monkeypatch):
    monkeypatch.setattr(locations, "get_location_by_name", lambda name: None)

    try:
        locations.location_tunnel("missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException")
