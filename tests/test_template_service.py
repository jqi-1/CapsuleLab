from pathlib import Path

from backend.services import template_service


def test_validate_catalog_includes_maintained_templates():
    result = template_service.validate_catalog()

    assert set(result) == set(template_service.MAINTAINED_TEMPLATES)


def test_validate_template_reports_expected_checks():
    checks = template_service.validate_template("python-basic")
    labels = {check.label for check in checks}

    assert "Dockerfile" in labels
    assert "Project config" in labels
    assert "README" in labels
    assert "Requirements" in labels
    assert "Starter notebook or app" in labels
    assert all(check.ok for check in checks)


def test_validate_unknown_template_fails():
    checks = template_service.validate_template("unknown-template", Path("/tmp/does-not-exist"))

    assert checks[0].ok is False
