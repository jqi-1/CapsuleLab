import subprocess
import shutil
import json
from pathlib import Path


class DockerError(Exception):
    def __init__(self, command: str, message: str, stderr: str = ""):
        self.command = command
        self.message = message
        self.stderr = stderr
        super().__init__(f"{message}\nCommand: {command}\n{stderr}")


def check_docker() -> bool:
    return shutil.which("docker") is not None


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
