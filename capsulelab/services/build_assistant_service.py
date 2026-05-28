from dataclasses import asdict, dataclass, field
from pathlib import Path

from capsulelab.db.repositories import builds, projects

READABLE_CONTEXT_FILES = [
    ".workbench/project.yaml",
    "Dockerfile",
    "requirements.txt",
    "apt.txt",
    "pyproject.toml",
    "preBuild.bash",
    "postBuild.bash",
]

WRITABLE_BUILD_SCRIPTS = {"preBuild.bash", "postBuild.bash"}


@dataclass
class BuildFinding:
    label: str
    detail: str
    severity: str = "warning"
    suggestion: str = ""


@dataclass
class ProposedBuildEdit:
    path: str
    action: str
    content: str
    rationale: str


@dataclass
class BuildAssistantReport:
    project_id: str
    project_path: str
    build_log_id: int | None
    build_status: str
    context_files: list[str] = field(default_factory=list)
    findings: list[BuildFinding] = field(default_factory=list)
    proposed_edits: list[ProposedBuildEdit] = field(default_factory=list)
    review_required: bool = True
    rebuild_triggered: bool = False

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "project_path": self.project_path,
            "build_log_id": self.build_log_id,
            "build_status": self.build_status,
            "context_files": self.context_files,
            "findings": [asdict(f) for f in self.findings],
            "proposed_edits": [asdict(e) for e in self.proposed_edits],
            "review_required": self.review_required,
            "rebuild_triggered": self.rebuild_triggered,
            "constraints": {
                "readable_files": READABLE_CONTEXT_FILES,
                "writable_files": sorted(WRITABLE_BUILD_SCRIPTS),
            },
        }


def analyze_failed_build(project_id: str, limit: int = 5) -> BuildAssistantReport:
    row = projects.get(project_id)
    if not row:
        raise ValueError(f"Project '{project_id}' not found")
    project_path = row["path"]
    latest = _latest_failed_log(project_id, limit=limit)
    report = BuildAssistantReport(
        project_id=project_id,
        project_path=project_path,
        build_log_id=latest.get("id") if latest else None,
        build_status=latest.get("status", "missing") if latest else "missing",
        context_files=_existing_context_files(project_path),
    )
    if not latest:
        report.findings.append(
            BuildFinding(
                label="No failed build log",
                detail="No failed build log is available for analysis.",
                severity="info",
                suggestion="Run `cap build` first, then retry the assistant if the build fails.",
            )
        )
        return report

    logs = latest.get("logs", "")
    _add_log_findings(report, logs)
    if not report.proposed_edits:
        report.findings.append(
            BuildFinding(
                label="No automatic build-script edit",
                detail="The failed log did not match the local assistant rules.",
                severity="info",
                suggestion=(
                    "Review the build log and edit requirements.txt, "
                    "apt.txt, preBuild.bash, or postBuild.bash manually."
                ),
            )
        )
    return report


def apply_proposed_edit(project_path: str, edit: ProposedBuildEdit) -> str:
    if edit.path not in WRITABLE_BUILD_SCRIPTS:
        raise ValueError(f"Build assistant can only write: {', '.join(sorted(WRITABLE_BUILD_SCRIPTS))}")
    path = Path(project_path) / edit.path
    existing = path.read_text() if path.exists() else "#!/usr/bin/env bash\nset -euo pipefail\n"
    marker = "# CapsuleLab build assistant suggestion"
    if edit.content in existing:
        return str(path)
    with open(path, "w") as f:
        f.write(existing.rstrip())
        f.write("\n\n")
        f.write(marker)
        f.write("\n")
        f.write(edit.content.rstrip())
        f.write("\n")
    return str(path)


def apply_first_proposed_edit(project_id: str) -> dict:
    report = analyze_failed_build(project_id)
    if not report.proposed_edits:
        return {"applied": False, "reason": "No proposed edits", "report": report.to_dict()}
    edit = report.proposed_edits[0]
    path = apply_proposed_edit(report.project_path, edit)
    return {"applied": True, "path": path, "edit": asdict(edit), "report": report.to_dict()}


def _latest_failed_log(project_id: str, limit: int = 5) -> dict | None:
    for row in builds.get_logs(project_id, limit=limit):
        if row.get("status") == "failed":
            return row
    return None


def _existing_context_files(project_path: str) -> list[str]:
    root = Path(project_path)
    return [name for name in READABLE_CONTEXT_FILES if (root / name).exists()]


def _add_log_findings(report: BuildAssistantReport, logs: str):
    lower = logs.lower()
    if "no matching distribution found" in lower or "could not find a version that satisfies" in lower:
        report.findings.append(
            BuildFinding(
                label="Python package resolution failed",
                detail="pip could not resolve one or more packages from the build log.",
                severity="error",
                suggestion="Check package names, Python version compatibility, and version pins in requirements.txt.",
            )
        )
        report.proposed_edits.append(
            ProposedBuildEdit(
                path="preBuild.bash",
                action="append",
                content="python -m pip install --upgrade pip setuptools wheel",
                rationale=(
                    "Upgrade packaging tools before dependency installation "
                    "so modern package metadata resolves correctly."
                ),
            )
        )
    if "unable to locate package" in lower or "e: package" in lower and "has no installation candidate" in lower:
        report.findings.append(
            BuildFinding(
                label="APT package resolution failed",
                detail="apt could not locate a system package.",
                severity="error",
                suggestion="Verify package names and apt repository setup before package installation.",
            )
        )
        report.proposed_edits.append(
            ProposedBuildEdit(
                path="preBuild.bash",
                action="append",
                content="sudo apt-get update",
                rationale="Refresh apt indexes before system package installation.",
            )
        )
    if "permission denied" in lower:
        report.findings.append(
            BuildFinding(
                label="Permission denied during build",
                detail="A build step failed with permission denied.",
                severity="error",
                suggestion=(
                    "Move privileged setup into preBuild.bash/postBuild.bash "
                    "and use sudo only for build-time system changes."
                ),
            )
        )
    if "command not found" in lower:
        report.findings.append(
            BuildFinding(
                label="Missing command during build",
                detail="A build command was not available in the image.",
                severity="warning",
                suggestion="Install the missing command via apt.txt or preBuild.bash before it is used.",
            )
        )
    if "cuda" in lower and ("not found" in lower or "no cuda" in lower):
        report.findings.append(
            BuildFinding(
                label="CUDA dependency mismatch",
                detail="The build log references missing CUDA components.",
                severity="warning",
                suggestion="Use a CUDA-capable base image or disable GPU-specific packages for CPU-only builds.",
            )
        )
