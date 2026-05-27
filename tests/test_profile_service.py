import yaml
from pathlib import Path

from backend.models.project import ProjectConfig
from backend.services import profile_service


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _template_config(path):
    return ProjectConfig(**yaml.safe_load((path / ".workbench" / "project.yaml").read_text()))


def _failed_labels(checks):
    return {check["label"] for check in checks if not check["ok"]}


def test_research_rag_template_satisfies_research_profile():
    template = TEMPLATES_DIR / "research-rag"
    checks = profile_service.check_profile_readiness(_template_config(template), str(template))

    assert "Research notebooks" not in _failed_labels(checks)
    assert "Research experiment notes" not in _failed_labels(checks)
    assert "Research source notes" not in _failed_labels(checks)
    assert "Research graph context" not in _failed_labels(checks)
    assert "Research reproducibility report" not in _failed_labels(checks)


def test_deployable_fastapi_template_satisfies_deployable_profile():
    template = TEMPLATES_DIR / "deployable-fastapi"
    checks = profile_service.check_profile_readiness(_template_config(template), str(template))

    assert "Deployable app healthcheck" not in _failed_labels(checks)
    assert "Deployable env example" not in _failed_labels(checks)
    assert "Deployable deployment manifest" not in _failed_labels(checks)
    assert "Deployable API tester" not in _failed_labels(checks)
    assert "Deployable secrets scan" not in _failed_labels(checks)
    assert "Deployable logging docs" not in _failed_labels(checks)


def test_opensource_package_template_satisfies_opensource_profile():
    template = TEMPLATES_DIR / "opensource-python-package"
    checks = profile_service.check_profile_readiness(_template_config(template), str(template))

    assert "Open-source docs" not in _failed_labels(checks)
    assert "Open-source CI" not in _failed_labels(checks)
    assert "Open-source changelog" not in _failed_labels(checks)
    assert "Open-source release checklist" not in _failed_labels(checks)
    assert "Open-source package metadata" not in _failed_labels(checks)
