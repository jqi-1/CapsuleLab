from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from capsulelab.core.project import ProjectConfig
from capsulelab.services import docker_service, gpu_service, ssh_service

PROJECT_LABEL = "com.capsulelab.project"


@dataclass
class RuntimeHealth:
    available: bool
    error: str = ""
    binary_found: bool = True
    daemon_running: bool = True
    socket_accessible: bool = True
    version: str = ""


@dataclass
class RuntimeStartPlan:
    project_path: str
    config: ProjectConfig
    container_name: str
    image: str
    mounts: list[tuple[str, str, bool]]
    ports: list[tuple[int, int]] | None
    gpu: bool
    labels: dict[str, str]
    env_vars: dict[str, str] | None


@dataclass
class RuntimeStartResult:
    status: str
    container: str
    image: str = ""
    gpu: bool = False
    detail: str = ""
    warnings: list[str] | None = None


@dataclass
class RuntimeStopResult:
    status: str
    container: str


@dataclass
class RuntimeStatusResult:
    container: str
    running: bool
    exists: bool
    health: RuntimeHealth


class RuntimeError(Exception):
    pass


class RuntimeUnavailable(RuntimeError):
    pass


class RuntimeConflict(RuntimeError):
    pass


class RuntimeAdapter(Protocol):
    def check_available(self) -> RuntimeHealth: ...

    def container_exists(self, container_name: str) -> bool: ...

    def is_running(self, container_name: str) -> bool: ...

    def inspect(self, container_name: str) -> dict: ...

    def get_used_ports(self) -> set[int]: ...

    def should_use_gpu(self, requested: bool) -> bool: ...

    def run(self, plan: RuntimeStartPlan) -> str: ...

    def stop(self, container_name: str) -> None: ...

    def logs(self, container_name: str, tail: int = 100, follow: bool = False) -> str: ...

    def exec(self, container_name: str, command: str, detach: bool = False) -> str: ...

    def exec_run(self, container_name: str, command: str, detach: bool = False) -> str: ...


class LocalDockerAdapter:
    def check_available(self) -> RuntimeHealth:
        status = docker_service.check_docker_status()
        return RuntimeHealth(
            available=status.available,
            error=status.error,
            binary_found=status.binary_found,
            daemon_running=status.daemon_running,
            socket_accessible=status.socket_accessible,
            version=status.version,
        )

    def container_exists(self, container_name: str) -> bool:
        return docker_service.container_exists(container_name)

    def is_running(self, container_name: str) -> bool:
        return docker_service.is_running(container_name)

    def inspect(self, container_name: str) -> dict:
        return docker_service.inspect(container_name)

    def get_used_ports(self) -> set[int]:
        return docker_service.get_used_ports()

    def should_use_gpu(self, requested: bool) -> bool:
        return bool(requested and gpu_service.detect_nvidia_smi())

    def run(self, plan: RuntimeStartPlan) -> str:
        return docker_service.run(
            container_name=plan.container_name,
            image_name=plan.image,
            mounts=plan.mounts,
            env_vars=plan.env_vars,
            gpu=plan.gpu,
            ports=plan.ports,
            labels=plan.labels,
        )

    def stop(self, container_name: str) -> None:
        docker_service.stop(container_name)

    def logs(self, container_name: str, tail: int = 100, follow: bool = False) -> str:
        return docker_service.logs(container_name, tail=tail, follow=follow)

    def exec(self, container_name: str, command: str, detach: bool = False) -> str:
        return docker_service.exec_run(container_name, command, detach=detach)

    def exec_run(self, container_name: str, command: str, detach: bool = False) -> str:
        return docker_service.exec_run(container_name, command, detach=detach)


class RemoteSSHAdapter:
    def __init__(self, location: dict, local_project_path: str):
        self.location = location
        self.local_project_path = local_project_path
        self.host = location["host"]
        self.user = location.get("user")
        self.remote_path = ssh_service.remote_project_path(local_project_path, location)

    def check_available(self) -> RuntimeHealth:
        status = ssh_service.check_status(self.host, self.user, self.remote_path)
        return RuntimeHealth(
            available=status.reachable and status.docker_available,
            error=status.error,
            version=status.docker_version,
        )

    def check_project(self, config: ProjectConfig, ports: list[int], require_gpu: bool):
        return ssh_service.check_remote_project(
            self.host,
            self.remote_path,
            config.runtime.dockerfile,
            ports=ports,
            user=self.user,
            require_gpu=require_gpu,
        )

    def container_exists(self, container_name: str) -> bool:
        return ssh_service.container_exists(self.host, container_name, self.user)

    def is_running(self, container_name: str) -> bool:
        return ssh_service.is_running(self.host, container_name, self.user)

    def inspect(self, container_name: str) -> dict:
        return ssh_service.inspect(self.host, container_name, self.user)

    def get_used_ports(self) -> set[int]:
        return set()

    def should_use_gpu(self, requested: bool) -> bool:
        return bool(requested and self.location.get("gpu"))

    def run(self, plan: RuntimeStartPlan) -> str:
        ports = [f"{host}:{container}" for host, container in plan.ports or []]
        return ssh_service.run(
            self.host,
            plan.container_name,
            plan.image,
            self.remote_path,
            plan.gpu,
            self.user,
            ports,
            env_vars=plan.env_vars,
            labels=plan.labels,
        )

    def stop(self, container_name: str) -> None:
        ssh_service.stop(self.host, container_name, self.user)

    def logs(self, container_name: str, tail: int = 100, follow: bool = False) -> str:
        return ssh_service.logs(self.host, container_name, tail=tail, user=self.user)

    def exec(self, container_name: str, command: str, detach: bool = False) -> str:
        return ssh_service.exec_run(self.host, container_name, command, self.user, detach=detach)

    def exec_run(self, container_name: str, command: str, detach: bool = False) -> str:
        return ssh_service.exec_run(self.host, container_name, command, self.user, detach=detach)


class RuntimeManager:
    def __init__(self, adapter: RuntimeAdapter):
        self.adapter = adapter

    def status(self, container_name: str) -> RuntimeStatusResult:
        health = self.adapter.check_available()
        if not health.available:
            return RuntimeStatusResult(container_name, False, False, health)
        return RuntimeStatusResult(
            container=container_name,
            running=self.adapter.is_running(container_name),
            exists=self.adapter.container_exists(container_name),
            health=health,
        )

    def start(self, project_path: str, config: ProjectConfig, container_name: str) -> RuntimeStartResult:
        health = self.adapter.check_available()
        if not health.available:
            raise RuntimeUnavailable(health.error)

        if self.adapter.is_running(container_name):
            return RuntimeStartResult("already_running", container_name)

        if self.adapter.container_exists(container_name):
            self._ensure_owned(container_name, config.name, action="replace")
            self.adapter.stop(container_name)

        plan = self._start_plan(project_path, config, container_name)
        self._check_ports(plan.ports)
        self._check_remote_project(config, plan)

        detail = self.adapter.run(plan)
        return RuntimeStartResult(
            status="started",
            container=container_name,
            image=plan.image,
            gpu=plan.gpu,
            detail=detail,
        )

    def stop(self, config: ProjectConfig, container_name: str) -> RuntimeStopResult:
        health = self.adapter.check_available()
        if not health.available:
            raise RuntimeUnavailable(health.error)

        if not self.adapter.container_exists(container_name):
            return RuntimeStopResult("not_found", container_name)

        self._ensure_owned(container_name, config.name, action="stop")
        self.adapter.stop(container_name)
        return RuntimeStopResult("stopped", container_name)

    def _start_plan(self, project_path: str, config: ProjectConfig, container_name: str) -> RuntimeStartPlan:
        mounts = []
        for mount in config.mounts:
            source = str(Path(project_path) / mount.source) if not Path(mount.source).is_absolute() else mount.source
            mounts.append((source, mount.target, mount.read_only))
        for cache in config.caches:
            source = str(Path(cache.source).expanduser())
            if Path(source).exists():
                mounts.append((source, cache.target, True))
        for dataset in config.datasets:
            source = str(Path(project_path) / dataset.path) if not Path(dataset.path).is_absolute() else dataset.path
            if Path(source).exists():
                mounts.append((source, dataset.target, dataset.read_only))

        ports = [(app.port, app.port) for app in config.apps if app.port is not None] if config.apps else None
        gpu = self.adapter.should_use_gpu(config.runtime.gpu)
        return RuntimeStartPlan(
            project_path=project_path,
            config=config,
            container_name=container_name,
            image=config.runtime.image or f"{config.name}:dev",
            mounts=mounts,
            ports=ports,
            gpu=gpu,
            labels={PROJECT_LABEL: config.name},
            env_vars=config.environment or None,
        )

    def _check_ports(self, ports: list[tuple[int, int]] | None) -> None:
        if not ports:
            return
        used_ports = self.adapter.get_used_ports()
        conflicts = [str(host_port) for host_port, _ in ports if host_port in used_ports]
        if conflicts:
            raise RuntimeConflict(
                f"Port conflict: port(s) {', '.join(conflicts)} already in use. "
                "Stop the other container or change the port mapping."
            )

    def _check_remote_project(self, config: ProjectConfig, plan: RuntimeStartPlan) -> None:
        check_project = getattr(self.adapter, "check_project", None)
        if check_project is None:
            return
        check = check_project(config, [host_port for host_port, _ in plan.ports or []], plan.gpu)
        if not check.docker_available:
            raise RuntimeUnavailable(f"Remote Docker is not available: {check.error or 'docker info failed'}")
        if not check.path_exists:
            raise RuntimeUnavailable(f"Remote project path does not exist: {check.remote_path}")
        if check.missing_files:
            raise RuntimeUnavailable(f"Remote project is missing required file(s): {', '.join(check.missing_files)}")
        if check.port_conflicts:
            raise RuntimeConflict(f"Remote port conflict: {', '.join(str(p) for p in check.port_conflicts)}")
        if plan.gpu and not check.gpu_available:
            plan.gpu = False

    def _ensure_owned(self, container_name: str, project_name: str, action: str) -> None:
        info = self.adapter.inspect(container_name)
        if not info:
            return
        labels = info.get("Config", {}).get("Labels", {}) or {}
        if labels.get(PROJECT_LABEL) == project_name:
            return
        if action == "replace":
            raise RuntimeConflict(
                f"Container '{container_name}' exists but is not owned by this project. "
                f"Remove it manually: docker rm -f {container_name}"
            )
        raise RuntimeConflict(f"Container '{container_name}' is not owned by this project. Refusing to stop.")
