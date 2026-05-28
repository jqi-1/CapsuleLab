from dataclasses import asdict, dataclass, field
from typing import Protocol

from capsulelab.core.errors import Severity
from capsulelab.core.project import ProjectConfig


@dataclass
class DoctorCheck:
    label: str
    severity: Severity
    ok: bool
    detail: str = ""
    suggestion: str = ""


@dataclass
class DoctorReport:
    project_name: str
    project_path: str
    checks: list[DoctorCheck] = field(default_factory=list)

    def all_ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def errors(self) -> list[DoctorCheck]:
        return [c for c in self.checks if c.severity in (Severity.ERROR, Severity.CRITICAL) and not c.ok]

    def warnings(self) -> list[DoctorCheck]:
        return [c for c in self.checks if c.severity == Severity.WARNING and not c.ok]

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "project_path": self.project_path,
            "all_ok": self.all_ok(),
            "checks": [asdict(c) for c in self.checks],
        }


class HealthCheckable(Protocol):
    def check_health(self, project_id: str, project_path: str, config: ProjectConfig) -> list[DoctorCheck]: ...
