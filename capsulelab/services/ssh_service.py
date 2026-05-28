import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from capsulelab.core.errors import CapsuleLabError, ErrorCode, Severity
from capsulelab.db.repositories import locations


class SSHError(CapsuleLabError):
    def __init__(self, message: str, detail: str = ""):
        code = (
            ErrorCode.SSH_UNREACHABLE
            if "connection failed" in message.lower() or "ssh:" in message.lower()
            else ErrorCode.GIT_ERROR
        )
        super().__init__(code, message, severity=Severity.ERROR, detail=detail)


class DockerError(SSHError):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(message, detail=detail)
        self.error_code = ErrorCode.DOCKER_UNAVAILABLE


class ProjectStateError(SSHError):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(message, detail=detail)
        self.error_code = ErrorCode.BAD_CONFIG


@dataclass
class RemoteStatus:
    reachable: bool
    docker_available: bool
    docker_version: str = ""
    gpu_available: bool = False
    gpu_name: str = ""
    project_path_exists: bool = False
    disk_total_gb: float = 0
    disk_free_gb: float = 0
    disk_used_percent: int = 0
    error: str = ""


@dataclass
class RemoteProjectCheck:
    remote_path: str
    path_exists: bool
    missing_files: list[str]
    port_conflicts: list[int]
    docker_available: bool
    gpu_available: bool
    error: str = ""


@dataclass
class TunnelSpec:
    proxy_port: int
    service_port: int
    remote_proxy_port: int = 10000
    remote_service_port: int = 10001

    def to_dict(self) -> dict:
        return {
            "proxy_port": self.proxy_port,
            "service_port": self.service_port,
            "remote_proxy_port": self.remote_proxy_port,
            "remote_service_port": self.remote_service_port,
        }


def _run_ssh(host: str, command: str, user: str | None = None, timeout: int = 60) -> str:
    ssh_user = f"{user}@" if user else ""
    args = [
        "ssh",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{ssh_user}{host}",
        command,
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            stderr = result.stderr.strip().lower()
            if "ssh:" in stderr or "permission denied" in stderr or "could not resolve" in stderr:
                raise SSHError(f"SSH connection failed: {result.stderr.strip()}")
            if "docker:" in stderr:
                raise DockerError(f"Docker command failed: {result.stderr.strip()}")
            raise SSHError(f"Remote command failed: {result.stderr.strip()}")
        return result.stdout.strip()
    except FileNotFoundError:
        raise SSHError("SSH client not found. Install OpenSSH.")
    except subprocess.TimeoutExpired:
        raise SSHError(f"Remote command timed out after {timeout}s")


def assign_tunnel_ports(location_id: str, start_port: int = 10000) -> TunnelSpec:
    existing = locations.get_tunnel(location_id)
    if existing:
        return TunnelSpec(proxy_port=existing["proxy_port"], service_port=existing["service_port"])
    used = {row["proxy_port"] for row in locations.list_tunnels()}
    used.update(row["service_port"] for row in locations.list_tunnels())
    proxy_port = start_port
    while proxy_port in used or proxy_port + 1 in used:
        proxy_port += 2
    service_port = proxy_port + 1
    locations.set_tunnel(location_id, proxy_port, service_port)
    return TunnelSpec(proxy_port=proxy_port, service_port=service_port)


def tunnel_command(location: dict, tunnel: TunnelSpec | None = None) -> list[str]:
    if tunnel is None:
        tunnel = assign_tunnel_ports(location["id"])
    user = location.get("user")
    host = location.get("host")
    target = f"{user}@{host}" if user else host
    return [
        "ssh",
        "-N",
        "-L",
        f"{tunnel.proxy_port}:localhost:{tunnel.remote_proxy_port}",
        "-L",
        f"{tunnel.service_port}:localhost:{tunnel.remote_service_port}",
        target,
    ]


def tunnel_info(location: dict) -> dict:
    tunnel = assign_tunnel_ports(location["id"])
    command = tunnel_command(location, tunnel)
    return {
        "location": location["name"],
        "host": location.get("host"),
        "user": location.get("user"),
        "proxy_url": f"http://localhost:{tunnel.proxy_port}",
        "service_url": f"http://localhost:{tunnel.service_port}",
        "ports": tunnel.to_dict(),
        "command": command,
        "command_text": " ".join(shlex.quote(part) for part in command),
    }


def check_status(host: str, user: str | None = None, remote_path: str | None = None) -> RemoteStatus:
    status = RemoteStatus(reachable=False, docker_available=False)
    try:
        _run_ssh(host, "echo reachable", user, timeout=10)
        status.reachable = True
    except SSHError as e:
        status.error = str(e)
        return status

    try:
        version = _run_ssh(host, "docker info --format '{{.ServerVersion}}'", user, timeout=15)
        status.docker_available = True
        status.docker_version = version
    except SSHError as e:
        status.error = str(e)

    if status.reachable:
        try:
            gpu_out = _run_ssh(host, "nvidia-smi --query-gpu=name --format=csv,noheader", user, timeout=15)
            status.gpu_available = True
            status.gpu_name = gpu_out.strip()
        except SSHError:
            pass

    if remote_path:
        try:
            out = _run_ssh(host, f"test -d {shlex.quote(remote_path)} && echo exists || echo missing", user, timeout=10)
            status.project_path_exists = out.strip() == "exists"
        except SSHError:
            pass

    if status.reachable:
        disk_path = remote_path or "."
        try:
            out = _run_ssh(
                host,
                f"df -Pk {shlex.quote(disk_path)} | tail -1 | awk '{{print $2, $3, $4, $5}}'",
                user,
                timeout=10,
            )
            parts = out.split()
            if len(parts) >= 4:
                total_kb = int(parts[0])
                free_kb = int(parts[2])
                status.disk_total_gb = round(total_kb / 1024 / 1024, 2)
                status.disk_free_gb = round(free_kb / 1024 / 1024, 2)
                status.disk_used_percent = int(parts[3].rstrip("%"))
        except (SSHError, ValueError):
            pass

    return status


def remote_project_path(local_project_path: str, location: dict) -> str:
    user = location.get("user")
    home = "/root" if not user else f"/home/{user}"
    remote_root = location.get("project_root") or f"{home}/capsulelab-projects"
    return str(Path(remote_root) / Path(local_project_path).name)


def check_remote_project(
    host: str,
    remote_path: str,
    dockerfile: str,
    ports: list[int] | None = None,
    user: str | None = None,
    require_gpu: bool = False,
) -> RemoteProjectCheck:
    status = check_status(host, user, remote_path)
    if not status.reachable:
        return RemoteProjectCheck(
            remote_path=remote_path,
            path_exists=False,
            missing_files=[],
            port_conflicts=[],
            docker_available=False,
            gpu_available=False,
            error=status.error,
        )

    missing_files: list[str] = []
    if status.project_path_exists:
        required = [".workbench/project.yaml", dockerfile]
        for rel_path in required:
            remote_file = str(Path(remote_path) / rel_path)
            try:
                out = _run_ssh(
                    host, f"test -f {shlex.quote(remote_file)} && echo exists || echo missing", user, timeout=10
                )
                if out.strip() != "exists":
                    missing_files.append(rel_path)
            except SSHError:
                missing_files.append(rel_path)

    port_conflicts: list[int] = []
    for port in ports or []:
        cmd = (
            f"if command -v ss >/dev/null 2>&1; then "
            f"ss -ltn | awk '{{print $4}}' | grep -Eq '[:.]'{port}'$' && echo used || echo free; "
            f"else echo unknown; fi"
        )
        try:
            out = _run_ssh(host, cmd, user, timeout=10)
            if out.strip() == "used":
                port_conflicts.append(port)
        except SSHError:
            pass

    gpu_available = status.gpu_available
    error = ""
    if require_gpu and not gpu_available:
        error = "GPU requested for this location, but nvidia-smi was not detected."

    return RemoteProjectCheck(
        remote_path=remote_path,
        path_exists=status.project_path_exists,
        missing_files=missing_files,
        port_conflicts=port_conflicts,
        docker_available=status.docker_available,
        gpu_available=gpu_available,
        error=error or status.error,
    )


def check_docker(host: str, user: str | None = None) -> bool:
    try:
        _run_ssh(host, "docker info --format '{{.ServerVersion}}'", user, timeout=15)
        return True
    except SSHError:
        return False


def check_gpu(host: str, user: str | None = None) -> bool:
    try:
        _run_ssh(host, "nvidia-smi --query-gpu=name --format=csv,noheader", user, timeout=15)
        return True
    except SSHError:
        return False


def sync_project(
    local_path: str,
    host: str,
    remote_path: str,
    user: str | None = None,
    dry_run: bool = False,
    exclude_patterns: list[str] | None = None,
) -> str:
    ssh_user = f"{user}@" if user else ""
    try:
        subprocess.run(
            ["ssh", f"{ssh_user}{host}", f"mkdir -p {shlex.quote(remote_path)}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise SSHError("Failed to create remote directory: timed out")

    default_excludes = [
        ".git/",
        "__pycache__/",
        "*.pyc",
        ".venv/",
        "venv/",
        ".DS_Store",
        ".cache/",
        ".trash/",
        ".local/share/Trash/",
        "*.sock",
        ".workbench/*.pid",
        "*.swp",
        "*.swo",
        ".cursor/",
        ".windsurf/",
    ]
    excludes = exclude_patterns or default_excludes
    rsync_args = [
        "rsync",
        "-avz",
        "--delete",
        "-e",
        "ssh -o StrictHostKeyChecking=accept-new",
    ]
    for pattern in excludes:
        rsync_args.extend(["--exclude", pattern])
    if dry_run:
        rsync_args.append("--dry-run")
    rsync_args.extend([f"{local_path}/", f"{ssh_user}{host}:{remote_path}/"])

    try:
        result = subprocess.run(rsync_args, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            detail = result.stderr.strip() or "Unknown rsync error"
            raise SSHError(f"rsync failed: {detail}")
        output = result.stdout.strip()
        if dry_run:
            detail_lines = [line for line in output.split("\n") if line.strip() and not line.startswith(".")]
            return f"Dry run — would transfer {len(detail_lines)} item(s)\n" + output
        return output
    except FileNotFoundError:
        raise SSHError("rsync not found. Install rsync.")
    except subprocess.TimeoutExpired:
        raise SSHError("rsync timed out after 300s")


def build(host: str, project_path: str, dockerfile: str, image_name: str, tag: str, user: str | None = None):
    df_path = Path(project_path) / dockerfile
    full_image = f"{image_name}:{tag}"
    cmd = " ".join(
        [
            "docker",
            "build",
            "-f",
            shlex.quote(str(df_path)),
            "-t",
            shlex.quote(full_image),
            shlex.quote(project_path),
        ]
    )
    try:
        return _run_ssh(host, cmd, user, timeout=600)
    except DockerError as e:
        raise DockerError(f"Remote build failed: {e}")
    except SSHError as e:
        raise SSHError(f"SSH failed during build: {e}")


def container_exists(host: str, container_name: str, user: str | None = None) -> bool:
    try:
        out = _run_ssh(
            host,
            f"docker ps -a --filter name=^{container_name}$ --format '{{{{.Names}}}}'",
            user,
            timeout=15,
        )
        return out == container_name
    except SSHError:
        return False


def is_running(host: str, container_name: str, user: str | None = None) -> bool:
    try:
        out = _run_ssh(
            host,
            f"docker ps --filter name=^{container_name}$ --format '{{{{.Names}}}}'",
            user,
            timeout=15,
        )
        return out == container_name
    except SSHError:
        return False


def run(
    host: str,
    container_name: str,
    image_name: str,
    project_path: str,
    gpu: bool,
    user: str | None = None,
    ports: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
    labels: dict[str, str] | None = None,
):
    args = ["docker", "run", "-d", "--name", container_name]
    if gpu:
        args.extend(["--gpus", "all"])
    args.extend(["-v", f"{project_path}:/workspace", "-w", "/workspace"])
    if ports:
        for p in ports:
            args.extend(["-p", p])
    if env_vars:
        for key, value in env_vars.items():
            args.extend(["-e", f"{key}={value}"])
    if labels:
        for key, value in labels.items():
            args.extend(["--label", f"{key}={value}"])
    args.extend([image_name, "sleep", "infinity"])
    try:
        return _run_ssh(host, " ".join(shlex.quote(arg) for arg in args), user, timeout=120)
    except DockerError as e:
        raise DockerError(f"Remote start failed: {e}")
    except SSHError as e:
        raise SSHError(f"SSH failed during start: {e}")


def stop(host: str, container_name: str, user: str | None = None):
    try:
        _run_ssh(host, f"docker stop {container_name} && docker rm {container_name}", user, timeout=60)
    except DockerError as e:
        raise DockerError(f"Remote stop failed: {e}")
    except SSHError as e:
        raise SSHError(f"SSH failed during stop: {e}")


def inspect(host: str, container_name: str, user: str | None = None) -> dict:
    try:
        out = _run_ssh(host, f"docker inspect {shlex.quote(container_name)}", user, timeout=15)
        data = json.loads(out)
        return data[0] if data else {}
    except DockerError as e:
        raise DockerError(f"Remote inspect failed: {e}")
    except SSHError as e:
        raise SSHError(f"SSH failed during inspect: {e}")
    except json.JSONDecodeError as e:
        raise DockerError(f"Remote inspect returned invalid JSON: {e}")


def logs(host: str, container_name: str, tail: int = 100, user: str | None = None) -> str:
    try:
        return _run_ssh(host, f"docker logs --tail {tail} {container_name}", user, timeout=30)
    except DockerError as e:
        raise DockerError(f"Remote logs failed: {e}")
    except SSHError as e:
        raise SSHError(f"SSH failed during logs: {e}")


def exec_run(host: str, container_name: str, command: str, user: str | None = None, detach: bool = False) -> str:
    detach_flag = "-d " if detach else ""
    cmd = f"docker exec {detach_flag}{container_name} sh -c {shlex.quote(command)}"
    try:
        return _run_ssh(host, cmd.strip(), user, timeout=120)
    except DockerError as e:
        raise DockerError(f"Remote exec failed: {e}")
    except SSHError as e:
        raise SSHError(f"SSH failed during exec: {e}")
