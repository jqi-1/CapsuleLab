import subprocess
import shutil
import json
from pathlib import Path
from dataclasses import dataclass
from capsulelab.core.errors import CapsuleLabError, ErrorCode, Severity


@dataclass
class DockerStatus:
    available: bool
    binary_found: bool
    daemon_running: bool
    socket_accessible: bool
    version: str = ""
    error: str = ""


def app_log_path(app_id: str) -> str:
    return f"/tmp/cap-{app_id}.log"


def parse_image_tag(image: str, default_tag: str = "dev") -> tuple[str, str]:
    if ":" in image:
        name, tag = image.rsplit(":", 1)
        return name, tag
    return image, default_tag


class DockerError(CapsuleLabError):
    def __init__(self, command: str, message: str, stderr: str = ""):
        self.command = command
        self.stderr = stderr
        code = ErrorCode.DOCKER_UNAVAILABLE
        sev = Severity.ERROR
        stderr_lower = stderr.lower()
        if "permission denied" in stderr_lower:
            code = ErrorCode.PERMISSION_DENIED
            sev = Severity.ERROR
        elif "not found" in stderr_lower or "no such image" in stderr_lower:
            code = ErrorCode.IMAGE_MISSING
        elif "port is already allocated" in stderr_lower:
            code = ErrorCode.PORT_CONFLICT
            sev = Severity.ERROR
        elif "timeout" in stderr_lower:
            code = ErrorCode.RUNTIME_TIMEOUT
            sev = Severity.CRITICAL
        elif "connection refused" in stderr_lower or "daemon" in stderr_lower:
            code = ErrorCode.DAEMON_DOWN
            sev = Severity.CRITICAL
        full_msg = f"{message}\nCommand: {command}\n{stderr}" if stderr else message
        super().__init__(code, full_msg, severity=sev, detail=stderr,
                         suggestion=DockerError._suggestion(code))
        self.message = message

    @staticmethod
    def _suggestion(code: ErrorCode) -> str:
        suggestions = {
            ErrorCode.PERMISSION_DENIED: "Add your user to the docker group: sudo usermod -aG docker $USER && newgrp docker",
            ErrorCode.DAEMON_DOWN: "Start Docker: sudo systemctl start docker (Linux) or open Docker Desktop.",
            ErrorCode.IMAGE_MISSING: "Run 'cap build' first, or check the image name in .workbench/project.yaml.",
            ErrorCode.PORT_CONFLICT: "Stop the other container using the port, or change the port mapping.",
        }
        return suggestions.get(code, "")


def check_docker() -> bool:
    return shutil.which("docker") is not None


def check_docker_status() -> DockerStatus:
    binary = shutil.which("docker")
    if not binary:
        return DockerStatus(
            available=False, binary_found=False,
            daemon_running=False, socket_accessible=False,
            error="Docker not found. Install Docker: https://docs.docker.com/engine/install/",
        )
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return DockerStatus(
                available=True, binary_found=True,
                daemon_running=True, socket_accessible=True,
                version=result.stdout.strip(),
            )
        stderr = result.stderr.strip().lower()
        if "permission denied" in stderr:
            return DockerStatus(
                available=False, binary_found=True,
                daemon_running=True, socket_accessible=False,
                error="Permission denied. Add your user to the 'docker' group: sudo usermod -aG docker $USER && newgrp docker",
            )
        return DockerStatus(
            available=False, binary_found=True,
            daemon_running=False, socket_accessible=False,
            error=result.stderr.strip(),
        )
    except subprocess.TimeoutExpired:
        return DockerStatus(
            available=False, binary_found=True,
            daemon_running=False, socket_accessible=False,
            error="Docker daemon not responding (timeout). Is Docker running?",
        )


def _run(args: list[str], timeout: int = 300, capture: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            args,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise DockerError(
                command=" ".join(args),
                message=f"Docker command failed with exit code {result.returncode}",
                stderr=result.stderr.strip(),
            )
        return result
    except FileNotFoundError:
        raise DockerError(command=" ".join(args), message="Docker not found. Is Docker installed?")
    except subprocess.TimeoutExpired:
        raise DockerError(command=" ".join(args), message=f"Command timed out after {timeout}s")


def build(project_path: str, dockerfile_path: str, image_name: str, tag: str = "dev") -> str:
    full_image = f"{image_name}:{tag}"
    df_path = Path(project_path) / dockerfile_path
    _run(
        ["docker", "build", "-f", str(df_path), "-t", full_image, "."],
        timeout=600,
    )
    return full_image


def build_with_logs(project_path: str, dockerfile_path: str, image_name: str, tag: str = "dev") -> tuple[str, str]:
    full_image = f"{image_name}:{tag}"
    df_path = Path(project_path) / dockerfile_path
    args = ["docker", "build", "-f", str(df_path), "-t", full_image, "."]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
        logs = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            raise DockerError(
                command=" ".join(args),
                message=f"Docker build failed with exit code {result.returncode}",
                stderr=result.stderr.strip(),
            )
        return full_image, logs
    except FileNotFoundError:
        raise DockerError(command=" ".join(args), message="Docker not found. Is Docker installed?")
    except subprocess.TimeoutExpired:
        raise DockerError(command=" ".join(args), message=f"Build timed out after 600s")


def run(
    container_name: str,
    image_name: str,
    mounts: list[tuple[str, str, bool]] | None = None,
    env_vars: dict[str, str] | None = None,
    gpu: bool = False,
    ports: list[tuple[int, int]] | None = None,
    labels: dict[str, str] | None = None,
    workdir: str = "/workspace",
) -> str:
    args = ["docker", "run", "-d", "--name", container_name]
    if gpu:
        args.extend(["--gpus", "all"])
    if mounts:
        for source, target, read_only in mounts:
            source_abs = str(Path(source).resolve())
            mount_spec = f"{source_abs}:{target}"
            if read_only:
                mount_spec += ":ro"
            args.extend(["-v", mount_spec])
    if env_vars:
        for key, value in env_vars.items():
            args.extend(["-e", f"{key}={value}"])
    if ports:
        for host_port, container_port in ports:
            args.extend(["-p", f"{host_port}:{container_port}"])
    if labels:
        for key, value in labels.items():
            args.extend(["--label", f"{key}={value}"])
    args.extend(["-w", workdir, image_name, "sleep", "infinity"])
    _run(args)
    return container_name


def stop(container_name: str):
    errors: list[str] = []
    try:
        _run(["docker", "stop", container_name])
    except DockerError as e:
        errors.append(str(e))
    try:
        _run(["docker", "rm", container_name])
    except DockerError as e:
        errors.append(str(e))
    if errors:
        raise DockerError("stop/rm", "Failed to fully remove container", "; ".join(errors))


def logs(container_name: str, tail: int = 100, follow: bool = False) -> str:
    args = ["docker", "logs"]
    if follow:
        args.append("--follow")
    if tail is not None:
        args.extend(["--tail", str(tail)])
    args.append(container_name)
    if follow:
        subprocess.run(args)
        return ""
    result = _run(args, timeout=30)
    return result.stdout


def exec_run(container_name: str, command: str, detach: bool = False) -> str:
    args = ["docker", "exec"]
    if detach:
        args.append("-d")
    args.extend([container_name, "sh", "-c", command])
    result = _run(args)
    return result.stdout.strip()


def exec_interactive(container_name: str, shell: str = "/bin/bash"):
    args = ["docker", "exec", "-it", container_name, shell]
    try:
        subprocess.run(args)
    except FileNotFoundError:
        args[-1] = "/bin/sh"
        subprocess.run(args)


def exec_command(container_name: str, command: str):
    args = ["docker", "exec", "-it", container_name, "sh", "-c", command]
    try:
        subprocess.run(args)
    except FileNotFoundError:
        raise DockerError("docker exec", f"Docker not found")


def ps(all_containers: bool = False) -> list[dict]:
    args = ["docker", "ps"]
    if all_containers:
        args.append("-a")
    args.extend(["--format", "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"])
    result = _run(args, timeout=15)
    containers = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 4:
            containers.append({
                "id": parts[0],
                "name": parts[1],
                "status": parts[2],
                "image": parts[3],
            })
    return containers


def container_exists(container_name: str) -> bool:
    for c in ps(all_containers=True):
        if c["name"] == container_name:
            return True
    return False


def is_running(container_name: str) -> bool:
    for c in ps(all_containers=False):
        if c["name"] == container_name:
            return True
    return False


def inspect(container_name: str) -> dict:
    result = _run(["docker", "inspect", container_name], timeout=15)
    data = json.loads(result.stdout)
    if data:
        return data[0]
    return {}


def inspect_image(image_name: str) -> dict:
    result = _run(["docker", "image", "inspect", image_name], timeout=15)
    data = json.loads(result.stdout)
    return data[0] if data else {}


def get_used_ports() -> set[int]:
    containers = ps(all_containers=False)
    used: set[int] = set()
    for c in containers:
        info = inspect(c["name"])
        if not info:
            continue
        network_settings = info.get("NetworkSettings", {}).get("Ports", {}) or {}
        for bindings in network_settings.values():
            if bindings:
                for b in bindings:
                    if b and "HostPort" in b:
                        try:
                            used.add(int(b["HostPort"]))
                        except (ValueError, TypeError):
                            pass
    return used
