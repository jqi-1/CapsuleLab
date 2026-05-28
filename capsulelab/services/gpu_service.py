from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from capsulelab.core.checks import DoctorCheck
from capsulelab.core.errors import Severity


@dataclass
class GpuInfo:
    available: bool
    name: str = ""
    vram_mb: int = 0
    driver_version: str = ""
    cuda_version: str = ""


def detect_nvidia_smi() -> bool:
    return shutil.which("nvidia-smi") is not None


def get_gpu_info() -> GpuInfo:
    if not detect_nvidia_smi():
        return GpuInfo(available=False)
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return GpuInfo(available=False)
        line = result.stdout.strip().split("\n")[0]
        if not line:
            return GpuInfo(available=False)
        parts = [p.strip() for p in line.split(",")]
        name = parts[0] if len(parts) > 0 else ""
        try:
            vram = int(parts[1]) if len(parts) > 1 and parts[1] != "[N/A]" else 0
        except (ValueError, IndexError):
            vram = 0
        driver = parts[2] if len(parts) > 2 else ""
        cuda = ""
        try:
            nvcc = subprocess.run(["nvcc", "--version"], capture_output=True, text=True, timeout=5)
            for line in nvcc.stdout.splitlines():
                if "release" in line:
                    cuda = line.split("release")[-1].strip().split(",")[0]
        except Exception:
            pass
        return GpuInfo(available=True, name=name, vram_mb=vram, driver_version=driver, cuda_version=cuda)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return GpuInfo(available=False)


def check_health(config=None) -> list[DoctorCheck]:
    gpu_info = get_gpu_info()
    checks = []
    if gpu_info.available:
        checks.append(
            DoctorCheck(
                label="GPU detected", severity=Severity.INFO, ok=True, detail=f"{gpu_info.name} ({gpu_info.vram_mb} MB)"
            )
        )
        docker_gpu = docker_gpu_available()
        checks.append(
            DoctorCheck(
                label="Docker GPU support",
                severity=Severity.WARNING,
                ok=docker_gpu,
                detail="Available" if docker_gpu else "nvidia-container-toolkit not configured",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                label="GPU detected",
                severity=Severity.INFO,
                ok=False,
                detail="No NVIDIA GPU found — running in CPU mode",
            )
        )

    if config and getattr(config.runtime, "gpu", False) and not gpu_info.available:
        checks.append(
            DoctorCheck(
                label="GPU requested",
                severity=Severity.WARNING,
                ok=False,
                detail="Project requires GPU but none detected",
                suggestion="Install NVIDIA drivers and nvidia-container-toolkit",
            )
        )

    return checks


def docker_gpu_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.Runtimes}}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return "nvidia" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
