from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from capsulelab.core.checks import DoctorCheck
from capsulelab.core.errors import CapsuleLabError, ErrorCode, Severity


class ComposeError(CapsuleLabError):
    def __init__(self, message: str, detail: str = ""):
        code = ErrorCode.COMPOSE_UNAVAILABLE if "not found" in message.lower() else ErrorCode.BUILD_FAILED
        super().__init__(code, message, severity=Severity.ERROR, detail=detail)


@dataclass
class ComposeDetection:
    available: bool
    binary: str
    compose_file: str | None
    error: str = ""


def compose_binary() -> str | None:
    if shutil.which("docker-compose"):
        return "docker-compose"
    if shutil.which("docker"):
        return "docker compose"
    return None


def find_compose_file(project_path: str) -> Path | None:
    for name in ["docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml"]:
        path = Path(project_path) / name
        if path.exists():
            return path
    return None


def detect(project_path: str) -> ComposeDetection:
    binary = compose_binary()
    compose_file = find_compose_file(project_path)
    if not binary:
        return ComposeDetection(False, "", str(compose_file) if compose_file else None, "Docker Compose not found")
    return ComposeDetection(True, binary, str(compose_file) if compose_file else None)


def _context(project_path: str) -> tuple[list[str], Path]:
    detection = detect(project_path)
    if not detection.available:
        raise ComposeError(detection.error)
    if not detection.compose_file:
        raise ComposeError("No docker-compose.yaml or compose.yaml found in project.")
    return detection.binary.split(), Path(detection.compose_file)


def _run(project_path: str, args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=project_path, capture_output=capture, text=True)
    if result.returncode != 0:
        raise ComposeError(result.stderr.strip() or f"Compose exited with code {result.returncode}")
    return result


def up(project_path: str, build: bool = False, detach: bool = True, profiles: list[str] | None = None) -> dict:
    binary, compose_file = _context(project_path)
    args = [*binary, "-f", str(compose_file), "up"]
    for profile in profiles or []:
        args.extend(["--profile", profile])
    if detach:
        args.append("-d")
    if build:
        args.append("--build")
    _run(project_path, args, capture=detach)
    return {"status": "started", "compose_file": compose_file.name, "profiles": profiles or []}


def down(project_path: str, volumes: bool = False) -> dict:
    binary, compose_file = _context(project_path)
    args = [*binary, "-f", str(compose_file), "down"]
    if volumes:
        args.append("-v")
    _run(project_path, args)
    return {"status": "stopped", "compose_file": compose_file.name}


def logs(project_path: str, service: str | None = None, tail: int = 50) -> str:
    binary, compose_file = _context(project_path)
    args = [*binary, "-f", str(compose_file), "logs", "--tail", str(tail)]
    if service:
        args.append(service)
    return _run(project_path, args).stdout


def ps(project_path: str) -> list[dict]:
    binary, compose_file = _context(project_path)
    json_args = [*binary, "-f", str(compose_file), "ps", "--format", "json"]
    try:
        result = _run(project_path, json_args)
        text = result.stdout.strip()
        if not text:
            return []
        if "\n" in text:
            data = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            data = json.loads(text)
        if isinstance(data, dict):
            data = [data]
        return [
            {
                "name": item.get("Name") or item.get("Name".lower()) or item.get("Service") or "",
                "service": item.get("Service") or item.get("Service".lower()) or "",
                "state": item.get("State") or item.get("State".lower()) or "",
                "health": item.get("Health") or item.get("Health".lower()) or "",
                "exit_code": item.get("ExitCode") or item.get("ExitCode".lower()),
                "ports": item.get("Ports") or item.get("Publishers") or "",
            }
            for item in data
        ]
    except (ComposeError, json.JSONDecodeError):
        result = _run(project_path, [*binary, "-f", str(compose_file), "ps"])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        return [{"name": line, "service": "", "state": "", "ports": ""} for line in lines[1:]]


def load_config(project_path: str) -> dict:
    compose_file = find_compose_file(project_path)
    if not compose_file:
        return {}
    with open(compose_file) as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ComposeError(f"Invalid Compose file: {compose_file.name}")
    return data


def profiles(project_path: str) -> list[str]:
    config = load_config(project_path)
    found: set[str] = set()
    for service in (config.get("services") or {}).values():
        for profile in _as_list(service.get("profiles")):
            found.add(str(profile))
    return sorted(found)


def service_definitions(project_path: str) -> list[dict]:
    config = load_config(project_path)
    services = config.get("services") or {}
    definitions = []
    for name, service in services.items():
        service = service or {}
        ports = _normalize_ports(service.get("ports") or [])
        trim_prefix = _env_truthy(service.get("environment"), "NVWB_TRIM_PREFIX")
        definitions.append(
            {
                "service": name,
                "image": service.get("image", ""),
                "build": service.get("build", ""),
                "profiles": _as_list(service.get("profiles")),
                "ports": ports,
                "web_access": trim_prefix,
                "urls": _service_urls(ports) if trim_prefix else [],
                "healthcheck": bool(service.get("healthcheck")),
                "depends_on": _depends_on(service.get("depends_on")),
                "gpu": _requests_gpu(service),
            }
        )
    return definitions


def validate(project_path: str) -> list[dict]:
    findings: list[dict] = []
    config = load_config(project_path)
    services = config.get("services") or {}
    if not services:
        findings.append({"severity": "warning", "label": "No services", "detail": "Compose file has no services."})
        return findings
    for service in service_definitions(project_path):
        if service["web_access"] and not service["ports"]:
            findings.append(
                {
                    "severity": "error",
                    "label": f"{service['service']}: web proxy port",
                    "detail": "NVWB_TRIM_PREFIX is enabled but no ports are exposed.",
                }
            )
        if service["depends_on"] and not service["healthcheck"]:
            findings.append(
                {
                    "severity": "info",
                    "label": f"{service['service']}: dependencies",
                    "detail": (
                        "Service has dependencies. Use healthchecks and "
                        "service_healthy conditions for readiness-sensitive stacks."
                    ),
                }
            )
        if service["gpu"] and "nvidia" not in json.dumps((services.get(service["service"]) or {})).lower():
            findings.append(
                {
                    "severity": "warning",
                    "label": f"{service['service']}: GPU configuration",
                    "detail": "GPU intent detected but NVIDIA runtime/device reservation is not explicit.",
                }
            )
    return findings


def service_statuses(definitions: list[dict], services: list[dict]) -> list[dict]:
    runtime_by_service = {service.get("service") or service.get("name"): service for service in services}
    statuses = []
    for definition in definitions:
        runtime = runtime_by_service.get(definition["service"], {})
        state = str(runtime.get("state") or "not_created").lower()
        health = str(runtime.get("health") or "").lower()
        if not health:
            if state in {"running", "up"} and definition.get("healthcheck"):
                health = "starting"
            elif state in {"running", "up"}:
                health = "unknown"
            elif state in {"exited", "dead"}:
                health = "stopped"
            else:
                health = "not_created"
        ok = state in {"running", "up"} and health not in {"unhealthy", "stopped"}
        statuses.append(
            {
                "service": definition["service"],
                "container": runtime.get("name", ""),
                "state": state,
                "health": health,
                "ok": ok,
                "profiles": definition["profiles"],
                "depends_on": definition["depends_on"],
                "ports": definition["ports"],
                "published_ports": _published_ports(definition["ports"], runtime.get("ports")),
                "urls": definition["urls"],
                "web_access": definition["web_access"],
                "gpu": definition["gpu"],
                "exit_code": runtime.get("exit_code"),
            }
        )
    for runtime in services:
        service_name = runtime.get("service") or runtime.get("name")
        if service_name and not any(status["service"] == service_name for status in statuses):
            state = str(runtime.get("state") or "unknown").lower()
            health = str(runtime.get("health") or "unknown").lower()
            statuses.append(
                {
                    "service": service_name,
                    "container": runtime.get("name", ""),
                    "state": state,
                    "health": health,
                    "ok": state in {"running", "up"} and health != "unhealthy",
                    "profiles": [],
                    "depends_on": [],
                    "ports": [],
                    "published_ports": _published_ports([], runtime.get("ports")),
                    "urls": [],
                    "web_access": False,
                    "gpu": False,
                    "exit_code": runtime.get("exit_code"),
                }
            )
    return statuses


def status(project_path: str) -> dict:
    detection = detect(project_path)
    services: list[dict] = []
    error = detection.error
    definitions: list[dict] = []
    found_profiles: list[str] = []
    findings: list[dict] = []
    if detection.available and detection.compose_file:
        try:
            services = ps(project_path)
            error = ""
        except ComposeError as e:
            error = str(e)
    if detection.compose_file:
        try:
            definitions = service_definitions(project_path)
            found_profiles = profiles(project_path)
            findings = validate(project_path)
        except ComposeError as e:
            error = str(e)
    return {
        "available": detection.available,
        "binary": detection.binary,
        "compose_file": Path(detection.compose_file).name if detection.compose_file else None,
        "detected": detection.compose_file is not None,
        "services": services,
        "definitions": definitions,
        "service_statuses": service_statuses(definitions, services),
        "profiles": found_profiles,
        "findings": findings,
        "runtime": {
            "kind": "compose",
            "ok": bool(definitions) and all(service["ok"] for service in service_statuses(definitions, services))
            if services
            else False,
            "service_count": len(definitions),
            "running_count": len(
                [service for service in services if str(service.get("state", "")).lower() in {"running", "up"}]
            ),
        },
        "error": error,
    }


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _normalize_ports(ports: list[Any]) -> list[dict]:
    normalized = []
    for port in ports:
        if isinstance(port, str):
            parts = port.split(":")
            if len(parts) == 1:
                normalized.append({"published": None, "target": _int_or_none(parts[0]), "raw": port})
            else:
                normalized.append(
                    {"published": _int_or_none(parts[-2]), "target": _int_or_none(parts[-1].split("/")[0]), "raw": port}
                )
        elif isinstance(port, dict):
            normalized.append(
                {
                    "published": _int_or_none(port.get("published")),
                    "target": _int_or_none(port.get("target")),
                    "raw": port,
                }
            )
    return normalized


def _service_urls(ports: list[dict]) -> list[str]:
    urls = []
    for port in ports:
        published = port.get("published") or port.get("target")
        if published:
            urls.append(f"http://localhost:{published}")
    return urls


def _published_ports(defined_ports: list[dict], runtime_ports: Any) -> list[int]:
    ports = [port.get("published") for port in defined_ports if port.get("published")]
    if isinstance(runtime_ports, list):
        for port in runtime_ports:
            if isinstance(port, dict):
                published = _int_or_none(port.get("PublishedPort") or port.get("published"))
                if published:
                    ports.append(published)
    elif isinstance(runtime_ports, str):
        for match in re.findall(r"(?:(?:0\.0\.0\.0|127\.0\.0\.1|localhost|\[::\]):)?(\d+)->", runtime_ports):
            parsed = _int_or_none(match)
            if parsed:
                ports.append(parsed)
    seen = []
    for port in ports:
        if port not in seen:
            seen.append(port)
    return seen


def check_health(project_path: str, config) -> list[DoctorCheck]:
    st = status(project_path)
    compose_expected = config.runtime.type.value == "compose" if config.runtime else False
    checks = []
    if st["detected"]:
        checks.append(
            DoctorCheck(label="Compose file", severity=Severity.INFO, ok=True, detail=st["compose_file"] or "Detected")
        )
        checks.append(
            DoctorCheck(
                label="Compose binary",
                severity=Severity.ERROR if compose_expected else Severity.WARNING,
                ok=st["available"],
                detail=st["binary"] or st["error"] or "Docker Compose not found",
            )
        )
        if st["available"]:
            detail = f"{len(st['services'])} service(s) visible" if st["services"] else "No running services"
            checks.append(DoctorCheck(label="Compose services", severity=Severity.INFO, ok=True, detail=detail))
    elif compose_expected:
        checks.append(
            DoctorCheck(
                label="Compose file",
                severity=Severity.ERROR,
                ok=False,
                detail="runtime.type is compose but no compose file was found",
            )
        )
    else:
        checks.append(
            DoctorCheck(label="Compose file", severity=Severity.INFO, ok=True, detail="Not a Compose project")
        )
    return checks


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _env_truthy(environment: Any, key: str) -> bool:
    if isinstance(environment, dict):
        return str(environment.get(key, "")).lower() == "true"
    if isinstance(environment, list):
        prefix = f"{key}="
        for item in environment:
            if str(item).startswith(prefix):
                return str(item).split("=", 1)[1].lower() == "true"
    return False


def _depends_on(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        return [str(key) for key in value.keys()]
    return []


def _requests_gpu(service: dict) -> bool:
    text = json.dumps(service).lower()
    return any(marker in text for marker in ["gpu", "nvidia", "cuda"])
