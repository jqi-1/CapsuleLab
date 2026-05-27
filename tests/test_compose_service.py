import subprocess

from capsulelab.services import compose_service


def test_find_compose_file(tmp_path):
    compose_file = tmp_path / "compose.yaml"
    compose_file.write_text("services: {}\n")

    assert compose_service.find_compose_file(str(tmp_path)) == compose_file


def test_detect_without_binary(monkeypatch, tmp_path):
    monkeypatch.setattr(compose_service, "compose_binary", lambda: None)

    status = compose_service.detect(str(tmp_path))

    assert status.available is False
    assert status.error == "Docker Compose not found"


def test_status_without_compose_file(monkeypatch, tmp_path):
    monkeypatch.setattr(compose_service, "compose_binary", lambda: "docker compose")

    status = compose_service.status(str(tmp_path))

    assert status["available"] is True
    assert status["detected"] is False
    assert status["services"] == []


def test_ps_parses_json(monkeypatch, tmp_path):
    (tmp_path / "compose.yaml").write_text("services: {}\n")
    monkeypatch.setattr(compose_service, "compose_binary", lambda: "docker compose")

    def fake_run(project_path, args, capture=True):
        return subprocess.CompletedProcess(args, 0, '[{"Name":"demo-web-1","Service":"web","State":"running","Ports":"0.0.0.0:8000->8000/tcp"}]', "")

    monkeypatch.setattr(compose_service, "_run", fake_run)

    services = compose_service.ps(str(tmp_path))

    assert services == [{
        "name": "demo-web-1",
        "service": "web",
        "state": "running",
        "health": "",
        "exit_code": None,
        "ports": "0.0.0.0:8000->8000/tcp",
    }]


def test_ps_parses_newline_delimited_json(monkeypatch, tmp_path):
    (tmp_path / "compose.yaml").write_text("services: {}\n")
    monkeypatch.setattr(compose_service, "compose_binary", lambda: "docker compose")

    def fake_run(project_path, args, capture=True):
        output = "\n".join([
            '{"Name":"demo-web-1","Service":"web","State":"running","Ports":"8000"}',
            '{"Name":"demo-db-1","Service":"db","State":"exited","Ports":""}',
        ])
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(compose_service, "_run", fake_run)

    services = compose_service.ps(str(tmp_path))

    assert [service["service"] for service in services] == ["web", "db"]


def test_service_definitions_detect_profiles_web_urls_health_and_dependencies(tmp_path):
    (tmp_path / "compose.yaml").write_text(
        """
services:
  frontend:
    image: demo/frontend:latest
    profiles: ["ui"]
    ports:
      - "3000:3000"
    environment:
      - NVWB_TRIM_PREFIX=true
    depends_on:
      backend:
        condition: service_healthy
  backend:
    image: demo/backend:latest
    ports:
      - target: 8080
        published: 8080
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
"""
    )

    definitions = compose_service.service_definitions(str(tmp_path))

    frontend = next(service for service in definitions if service["service"] == "frontend")
    backend = next(service for service in definitions if service["service"] == "backend")
    assert frontend["profiles"] == ["ui"]
    assert frontend["web_access"] is True
    assert frontend["urls"] == ["http://localhost:3000"]
    assert frontend["depends_on"] == ["backend"]
    assert backend["healthcheck"] is True


def test_profiles_returns_sorted_unique_profiles(tmp_path):
    (tmp_path / "compose.yaml").write_text(
        """
services:
  api:
    image: api
    profiles: [gpu, dev]
  worker:
    image: worker
    profiles: gpu
"""
    )

    assert compose_service.profiles(str(tmp_path)) == ["dev", "gpu"]


def test_validate_flags_web_service_without_ports(tmp_path):
    (tmp_path / "compose.yaml").write_text(
        """
services:
  app:
    image: app
    environment:
      NVWB_TRIM_PREFIX: "true"
"""
    )

    findings = compose_service.validate(str(tmp_path))

    assert findings[0]["severity"] == "error"
    assert "web proxy port" in findings[0]["label"]


def test_status_includes_static_compose_metadata_without_binary(monkeypatch, tmp_path):
    (tmp_path / "compose.yaml").write_text(
        """
services:
  app:
    image: app
    ports:
      - "8501:8501"
    environment:
      NVWB_TRIM_PREFIX: "true"
"""
    )
    monkeypatch.setattr(compose_service, "compose_binary", lambda: None)

    status = compose_service.status(str(tmp_path))

    assert status["available"] is False
    assert status["detected"] is True
    assert status["definitions"][0]["service"] == "app"
    assert status["definitions"][0]["urls"] == ["http://localhost:8501"]
    assert status["service_statuses"][0]["state"] == "not_created"


def test_status_combines_compose_runtime_health_ports_and_urls(monkeypatch, tmp_path):
    (tmp_path / "compose.yaml").write_text(
        """
services:
  app:
    image: app
    ports:
      - "8501:8501"
    environment:
      NVWB_TRIM_PREFIX: "true"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/health"]
  worker:
    image: worker
    depends_on:
      - app
"""
    )
    monkeypatch.setattr(compose_service, "compose_binary", lambda: "docker compose")

    def fake_run(project_path, args, capture=True):
        output = "\n".join([
            '{"Name":"demo-app-1","Service":"app","State":"running","Health":"healthy","Ports":"0.0.0.0:8501->8501/tcp"}',
            '{"Name":"demo-worker-1","Service":"worker","State":"exited","ExitCode":1,"Ports":""}',
        ])
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(compose_service, "_run", fake_run)

    status = compose_service.status(str(tmp_path))
    app = next(service for service in status["service_statuses"] if service["service"] == "app")
    worker = next(service for service in status["service_statuses"] if service["service"] == "worker")

    assert app["state"] == "running"
    assert app["health"] == "healthy"
    assert app["ok"] is True
    assert app["published_ports"] == [8501]
    assert app["urls"] == ["http://localhost:8501"]
    assert worker["state"] == "exited"
    assert worker["health"] == "stopped"
    assert worker["ok"] is False
    assert worker["depends_on"] == ["app"]
    assert status["runtime"]["kind"] == "compose"
    assert status["runtime"]["ok"] is False
    assert status["runtime"]["running_count"] == 1


def test_up_passes_profiles_before_detach(monkeypatch, tmp_path):
    (tmp_path / "compose.yaml").write_text("services: {}\n")
    monkeypatch.setattr(compose_service, "compose_binary", lambda: "docker compose")
    calls = []

    def fake_run(project_path, args, capture=True):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(compose_service, "_run", fake_run)

    result = compose_service.up(str(tmp_path), profiles=["ui", "gpu"])

    assert result["profiles"] == ["ui", "gpu"]
    assert "--profile" in calls[0]
    assert calls[0].count("--profile") == 2
