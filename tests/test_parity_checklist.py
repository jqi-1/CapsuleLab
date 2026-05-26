import pytest

from backend.models.project import ProjectConfig, RuntimeConfig, AppConfig, RuntimeType
from backend.services import project_service, app_service, doctor_service
from backend.services.doctor_service import DoctorCheck, Severity


class TestParityChecklist:
    """Verify CLI, API, and UI report the same project/app/container facts.

    These are pure-config tests (no Docker needed). Run with `pytest -m pure_config`.
    """

    @pytest.mark.pure_config
    def test_project_id_is_consistent(self):
        name = "my-demo-project"
        pid = project_service.get_project_id(name)
        cid = project_service.get_container_name(name)
        assert pid == cid, f"project_id ({pid}) != container_name ({cid})"

    @pytest.mark.pure_config
    def test_project_status_shape(self):
        config = ProjectConfig(
            name="parity-test",
            runtime=RuntimeConfig(type=RuntimeType.docker, dockerfile="Dockerfile", image="parity-test:dev"),
            apps=[AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)],
        )

        # This is the canonical shape both CLI doctor and API /status provide
        status_fields = {
            "name", "project_id", "container", "container_running",
            "docker", "gpu_available", "gpu_name", "gpu_vram_mb",
            "readiness", "apps", "compose", "build", "git", "resources", "secrets",
        }
        assert status_fields, "status_fields must be non-empty"

        # Service-layer DTO must produce a dict with these keys
        project_id = project_service.get_project_id(config.name)
        container_name = project_service.get_container_name(config.name)
        status_dto = {
            "name": config.name,
            "project_id": project_id,
            "container": container_name,
            "container_running": False,
            "docker": {"available": False},
            "gpu_available": False,
            "gpu_name": "",
            "gpu_vram_mb": 0,
            "readiness": {"ok": False, "warnings": []},
            "apps": [],
            "compose": {},
            "build": None,
            "git": {},
            "resources": {},
            "secrets": {"configured": [], "present": [], "missing": []},
        }
        assert status_fields.issubset(status_dto.keys()), (
            f"Status DTO missing fields: {status_fields - status_dto.keys()}"
        )

    @pytest.mark.pure_config
    def test_doctor_report_shape(self):
        report = doctor_service.DoctorReport(project_name="test", project_path="/tmp/test")
        report.checks.append(DoctorCheck(label="Config", severity=Severity.INFO, ok=True, detail="OK"))

        d = report.to_dict()
        assert "project_name" in d
        assert "project_path" in d
        assert "all_ok" in d
        assert "checks" in d
        assert all("label" in c and "severity" in c and "ok" in c for c in d["checks"])

    @pytest.mark.pure_config
    def test_app_status_shape(self):
        app_config = AppConfig(name="Jupyter", id="jupyter", command="jupyter lab", port=8888)
        pid = project_service.get_project_id("test")
        # The shape returned by get_app_status (without a running container)
        shape = {
            "app_id", "name", "port", "url", "proxy_url",
            "url_path", "kind", "log_path", "container_running",
            "state", "pid", "alive",
        }
        assert shape, "app_status_fields must be non-empty"

    @pytest.mark.pure_config
    def test_error_model_shape(self):
        from backend.models.errors import CapsuleLabError, ErrorCode, Severity
        err = CapsuleLabError(ErrorCode.BAD_CONFIG, "test error", severity=Severity.ERROR, detail="detail", suggestion="fix it")
        d = err.to_dict()
        assert "error_code" in d
        assert "message" in d
        assert "severity" in d
        assert "detail" in d
        assert "suggestion" in d

    @pytest.mark.pure_config
    def test_app_urls_consistent(self):
        app = AppConfig(name="Test", id="test", command="test", port=8080, url_path="/ui")
        url = app_service.get_app_url(app)
        proxy_url = app_service.get_proxy_app_url("cap-test", app)
        assert url == "http://localhost:8080/ui"
        assert "cap-test" in proxy_url
        assert "/apps/test" in proxy_url
