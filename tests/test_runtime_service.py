import pytest

from backend.models.project import AppConfig, Mount, ProjectConfig, RuntimeConfig
from backend.services import runtime_service


class FakeAdapter:
    def __init__(self):
        self.health = runtime_service.RuntimeHealth(available=True)
        self.exists = False
        self.running = False
        self.info = {}
        self.used_ports: set[int] = set()
        self.stopped: list[str] = []
        self.runs: list[runtime_service.RuntimeStartPlan] = []

    def check_available(self):
        return self.health

    def container_exists(self, container_name):
        return self.exists

    def is_running(self, container_name):
        return self.running

    def inspect(self, container_name):
        return self.info

    def get_used_ports(self):
        return self.used_ports

    def should_use_gpu(self, requested):
        return requested

    def run(self, plan):
        self.runs.append(plan)
        return "started-id"

    def stop(self, container_name):
        self.stopped.append(container_name)

    def logs(self, container_name, tail=100, follow=False):
        return ""

    def exec(self, container_name, command, detach=False):
        return ""


def test_runtime_manager_starts_with_resolved_mounts_and_ports(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    dataset_dir = tmp_path / "data"
    dataset_dir.mkdir()
    config = ProjectConfig(
        name="demo",
        runtime=RuntimeConfig(image="demo:dev", gpu=True),
        mounts=[Mount(source=".", target="/workspace")],
        caches=[],
        datasets=[{"name": "data", "path": "data", "target": "/data"}],
        environment={"TOKEN": "secret"},
        apps=[AppConfig(name="Notebook", id="jupyter", command="jupyter", port=8888)],
    )
    adapter = FakeAdapter()

    result = runtime_service.RuntimeManager(adapter).start(str(tmp_path), config, "cap-demo")

    assert result.status == "started"
    assert adapter.runs[0].mounts == [
        (str(tmp_path / "."), "/workspace", False),
        (str(dataset_dir), "/data", True),
    ]
    assert adapter.runs[0].ports == [(8888, 8888)]
    assert adapter.runs[0].env_vars == {"TOKEN": "secret"}
    assert adapter.runs[0].labels == {runtime_service.PROJECT_LABEL: "demo"}
    assert adapter.runs[0].gpu is True


def test_runtime_manager_replaces_owned_existing_container():
    config = ProjectConfig(name="demo", runtime=RuntimeConfig(image="demo:dev"))
    adapter = FakeAdapter()
    adapter.exists = True
    adapter.info = {"Config": {"Labels": {runtime_service.PROJECT_LABEL: "demo"}}}

    runtime_service.RuntimeManager(adapter).start("/tmp/demo", config, "cap-demo")

    assert adapter.stopped == ["cap-demo"]
    assert len(adapter.runs) == 1


def test_runtime_manager_refuses_unowned_existing_container():
    config = ProjectConfig(name="demo", runtime=RuntimeConfig(image="demo:dev"))
    adapter = FakeAdapter()
    adapter.exists = True
    adapter.info = {"Config": {"Labels": {runtime_service.PROJECT_LABEL: "other"}}}

    with pytest.raises(runtime_service.RuntimeConflict):
        runtime_service.RuntimeManager(adapter).start("/tmp/demo", config, "cap-demo")

    assert adapter.stopped == []
    assert adapter.runs == []


def test_runtime_manager_detects_port_conflicts():
    config = ProjectConfig(
        name="demo",
        runtime=RuntimeConfig(image="demo:dev"),
        apps=[AppConfig(name="Notebook", id="jupyter", command="jupyter", port=8888)],
    )
    adapter = FakeAdapter()
    adapter.used_ports = {8888}

    with pytest.raises(runtime_service.RuntimeConflict):
        runtime_service.RuntimeManager(adapter).start("/tmp/demo", config, "cap-demo")


def test_runtime_manager_status_does_not_touch_container_when_unavailable():
    adapter = FakeAdapter()
    adapter.health = runtime_service.RuntimeHealth(available=False, error="offline")
    adapter.exists = True
    adapter.running = True

    status = runtime_service.RuntimeManager(adapter).status("cap-demo")

    assert status.running is False
    assert status.exists is False
    assert status.health.error == "offline"
