from enum import Enum


class ErrorCode(str, Enum):
    DOCKER_UNAVAILABLE = "docker_unavailable"
    DAEMON_DOWN = "daemon_down"
    PERMISSION_DENIED = "permission_denied"
    IMAGE_MISSING = "image_missing"
    BAD_CONFIG = "bad_config"
    PORT_CONFLICT = "port_conflict"
    GPU_UNAVAILABLE = "gpu_unavailable"
    MISSING_SECRET = "missing_secret"
    MISSING_DATASET = "missing_dataset"
    STALE_RUNTIME_STATE = "stale_runtime_state"
    CONTAINER_NOT_FOUND = "container_not_found"
    APP_NOT_FOUND = "app_not_found"
    SSH_UNREACHABLE = "ssh_unreachable"
    COMPOSE_UNAVAILABLE = "compose_unavailable"
    BUILD_FAILED = "build_failed"
    TEMPLATE_NOT_FOUND = "template_not_found"
    RUNTIME_TIMEOUT = "runtime_timeout"
    RSYNC_FAILED = "rsync_failed"
    DOCKER_GPU_NOT_CONFIGURED = "docker_gpu_not_configured"
    PROJECT_NOT_FOUND = "project_not_found"
    GIT_ERROR = "git_error"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CapsuleLabError(Exception):
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        severity: Severity = Severity.ERROR,
        detail: str = "",
        suggestion: str = "",
    ):
        self.error_code = error_code
        self.severity = severity
        self.detail = detail
        self.suggestion = suggestion
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code.value,
            "message": str(self.args[0]),
            "severity": self.severity.value,
            "detail": self.detail,
            "suggestion": self.suggestion,
        }


class DockerUnavailableError(CapsuleLabError):
    def __init__(self, detail: str = "", suggestion: str = ""):
        super().__init__(
            error_code=ErrorCode.DOCKER_UNAVAILABLE,
            message="Docker is not available",
            severity=Severity.CRITICAL,
            detail=detail or "The docker binary or daemon is not reachable.",
            suggestion=suggestion
            or "Install Docker (https://docs.docker.com/engine/install/) and ensure the daemon is running.",
        )


class DaemonDownError(CapsuleLabError):
    def __init__(self, detail: str = ""):
        super().__init__(
            error_code=ErrorCode.DAEMON_DOWN,
            message="Docker daemon is not responding",
            severity=Severity.CRITICAL,
            detail=detail or "Docker daemon may not be running.",
            suggestion="Start Docker: sudo systemctl start docker (Linux) or open Docker Desktop.",
        )


class PermissionDeniedError(CapsuleLabError):
    def __init__(self):
        super().__init__(
            error_code=ErrorCode.PERMISSION_DENIED,
            message="Permission denied accessing Docker",
            severity=Severity.ERROR,
            detail="Your user does not have permission to access the Docker socket.",
            suggestion="Add your user to the docker group: sudo usermod -aG docker $USER && newgrp docker",
        )


class ImageMissingError(CapsuleLabError):
    def __init__(self, image: str, detail: str = ""):
        super().__init__(
            error_code=ErrorCode.IMAGE_MISSING,
            message=f"Image '{image}' not found",
            severity=Severity.ERROR,
            detail=detail or f"The Docker image '{image}' is not available locally and could not be pulled.",
            suggestion="Run 'cap build' first, or check the image name in .workbench/project.yaml.",
        )


class BadConfigError(CapsuleLabError):
    def __init__(self, detail: str):
        super().__init__(
            error_code=ErrorCode.BAD_CONFIG,
            message="Invalid project configuration",
            severity=Severity.ERROR,
            detail=detail,
            suggestion="Check .workbench/project.yaml for errors and run 'cap doctor' for details.",
        )


class PortConflictError(CapsuleLabError):
    def __init__(self, ports: list[int]):
        super().__init__(
            error_code=ErrorCode.PORT_CONFLICT,
            message=f"Port conflict on {', '.join(str(p) for p in ports)}",
            severity=Severity.ERROR,
            detail=f"The following port(s) are already in use: {', '.join(str(p) for p in ports)}",
            suggestion=(
                "Stop the other container using the port, or change the port mapping in .workbench/project.yaml."
            ),
        )


class GpuUnavailableError(CapsuleLabError):
    def __init__(self, detail: str = ""):
        super().__init__(
            error_code=ErrorCode.GPU_UNAVAILABLE,
            message="GPU requested but not available",
            severity=Severity.WARNING,
            detail=detail
            or "The project requests GPU (gpu: true) but no NVIDIA GPU or nvidia-container-toolkit was detected.",
            suggestion="Ensure nvidia-smi works and nvidia-container-toolkit is installed for Docker GPU support.",
        )


class MissingSecretError(CapsuleLabError):
    def __init__(self, secrets: list[str]):
        super().__init__(
            error_code=ErrorCode.MISSING_SECRET,
            message=f"Required secret(s) missing: {', '.join(secrets)}",
            severity=Severity.WARNING,
            detail=f"The following required secrets are not set: {', '.join(secrets)}",
            suggestion="Set them with: cap secrets set <name>",
        )


class MissingDatasetError(CapsuleLabError):
    def __init__(self, dataset: str, path: str):
        super().__init__(
            error_code=ErrorCode.MISSING_DATASET,
            message=f"Dataset '{dataset}' not found at {path}",
            severity=Severity.WARNING,
            detail=f"The dataset path '{path}' does not exist on this machine.",
            suggestion="Place the dataset at the expected path or update the dataset path in .workbench/project.yaml.",
        )


class StaleRuntimeStateError(CapsuleLabError):
    def __init__(self, detail: str = ""):
        super().__init__(
            error_code=ErrorCode.STALE_RUNTIME_STATE,
            message="Stale runtime state detected",
            severity=Severity.WARNING,
            detail=detail or "The runtime state may be out of sync with the actual container.",
            suggestion="Stop and start the project to reset runtime state.",
        )


class ContainerNotFoundError(CapsuleLabError):
    def __init__(self, container_name: str):
        super().__init__(
            error_code=ErrorCode.CONTAINER_NOT_FOUND,
            message=f"Container '{container_name}' not found",
            severity=Severity.ERROR,
            detail=f"No container named '{container_name}' exists (running or stopped).",
            suggestion="Start the project first with: cap start",
        )


class AppNotFoundError(CapsuleLabError):
    def __init__(self, app_id: str):
        super().__init__(
            error_code=ErrorCode.APP_NOT_FOUND,
            message=f"App '{app_id}' not found",
            severity=Severity.ERROR,
            detail=f"App '{app_id}' is not defined in the project configuration.",
            suggestion="Check the apps section in .workbench/project.yaml.",
        )


class SshUnreachableError(CapsuleLabError):
    def __init__(self, host: str, detail: str = ""):
        super().__init__(
            error_code=ErrorCode.SSH_UNREACHABLE,
            message=f"SSH host '{host}' is not reachable",
            severity=Severity.ERROR,
            detail=detail or f"Cannot connect to {host} via SSH.",
            suggestion="Check the hostname, network connectivity, and SSH credentials.",
        )


class ComposeUnavailableError(CapsuleLabError):
    def __init__(self, detail: str = ""):
        super().__init__(
            error_code=ErrorCode.COMPOSE_UNAVAILABLE,
            message="Docker Compose is not available",
            severity=Severity.ERROR,
            detail=detail or "Neither 'docker compose' nor 'docker-compose' was found.",
            suggestion="Install Docker Compose: https://docs.docker.com/compose/install/",
        )


class BuildFailedError(CapsuleLabError):
    def __init__(self, detail: str = "", logs: str = ""):
        super().__init__(
            error_code=ErrorCode.BUILD_FAILED,
            message="Docker build failed",
            severity=Severity.ERROR,
            detail=detail or "The Docker image build failed.",
            suggestion="Check the Dockerfile and build logs for errors.",
        )
        self.logs = logs

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["logs"] = self.logs
        return d


class GitError_(CapsuleLabError):
    def __init__(self, detail: str = ""):
        super().__init__(
            error_code=ErrorCode.GIT_ERROR,
            message="Git operation failed",
            severity=Severity.ERROR,
            detail=detail,
            suggestion="Check that git is installed and the repository is in a valid state.",
        )
