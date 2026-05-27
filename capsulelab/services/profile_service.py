from capsulelab.core.project import (
    ProjectMode, ProjectConfig, default_presets,
    RESEARCH_PRESETS, DEPLOYABLE_PRESETS, OPENSOURCE_PRESETS,
)


PROFILE_METADATA = {
    ProjectMode.research: {
        "label": "Research",
        "description": "Notebook-first experiments, papers, datasets, models, run comparison, reports, and knowledge graphs",
        "icon": "🔬",
        "recommended_apps": ["jupyter", "tensorboard", "mlflow"],
        "required_dirs": ["notebooks"],
        "optional_dirs": ["experiments", "papers", "outputs", "reports"],
    },
    ProjectMode.deployable: {
        "label": "Deployable",
        "description": "API/service/app packaging, Docker checks, health checks, secrets, tests, logs, and deployment manifests",
        "icon": "🚀",
        "recommended_apps": ["fastapi", "gradio", "streamlit"],
        "required_dirs": ["app", "tests", "configs"],
        "optional_dirs": ["docker", "scripts", "docs"],
    },
    ProjectMode.opensource: {
        "label": "Open Source",
        "description": "Public project polish: README, license, contributing, docs, examples, package metadata, CI, and release readiness",
        "icon": "🌐",
        "recommended_apps": [],
        "required_dirs": ["src", "tests", "docs", "examples"],
        "optional_dirs": ["scripts", "assets", ".github"],
    },
}


def get_profile(mode: ProjectMode | None) -> dict:
    if mode is None:
        return {"mode": None, "label": "None", "presets": {}}
    meta = PROFILE_METADATA.get(mode, {})
    presets = default_presets(mode)
    return {
        "mode": mode.value,
        "label": meta.get("label", mode.value),
        "description": meta.get("description", ""),
        "icon": meta.get("icon", ""),
        "presets": presets,
        "recommended_apps": meta.get("recommended_apps", []),
        "required_dirs": meta.get("required_dirs", []),
        "optional_dirs": meta.get("optional_dirs", []),
    }


def list_profiles() -> list[dict]:
    return [get_profile(m) for m in ProjectMode]


def templates_for_mode(mode: ProjectMode | None, template_manifest: dict) -> list[tuple[str, dict]]:
    results = []
    for name, meta in template_manifest.items():
        tmpl_mode = meta.get("mode", "research")
        if mode is None or tmpl_mode == mode.value:
            results.append((name, meta))
    return results


def check_profile_readiness(config: ProjectConfig, project_path: str) -> list[dict]:
    from pathlib import Path
    checks: list[dict] = []
    proj = Path(project_path)

    if config.mode is None:
        return checks

    meta = PROFILE_METADATA.get(config.mode, {})
    for d in meta.get("required_dirs", []):
        exists = (proj / d).exists()
        checks.append({
            "label": f"Required directory: {d}/",
            "ok": exists,
            "detail": "Found" if exists else f"Missing — create {proj / d}",
            "severity": "error",
        })

    for d in meta.get("optional_dirs", []):
        exists = (proj / d).exists()
        checks.append({
            "label": f"Optional directory: {d}/",
            "ok": True,
            "detail": "Found" if exists else "Not present (optional)",
            "severity": "info",
        })

    for preset_name, expected in config.presets.items():
        if expected:
            checks.append({
                "label": f"Preset: {preset_name}",
                "ok": True,
                "detail": "Enabled",
                "severity": "info",
            })

    if config.mode == ProjectMode.research:
        checks.extend(_research_checks(proj, config))
    elif config.mode == ProjectMode.deployable:
        checks.extend(_deployable_checks(proj, config))
    elif config.mode == ProjectMode.opensource:
        checks.extend(_opensource_checks(proj))

    return checks


def _check(label: str, ok: bool, detail: str, severity: str = "error") -> dict:
    return {"label": label, "ok": ok, "detail": detail, "severity": severity}


def _any_exists(project_path, candidates: list[str]) -> tuple[bool, str]:
    for candidate in candidates:
        if (project_path / candidate).exists():
            return True, candidate
    return False, ", ".join(candidates)


def _research_checks(proj, config: ProjectConfig) -> list[dict]:
    checks: list[dict] = []
    notebooks = list((proj / "notebooks").glob("*.ipynb")) if (proj / "notebooks").exists() else []
    checks.append(_check("Research notebooks", bool(notebooks), f"{len(notebooks)} notebook(s)" if notebooks else "Missing notebooks/*.ipynb"))

    has_dataset_intent = bool(config.datasets) or (proj / "data").exists()
    checks.append(_check("Research dataset workspace", has_dataset_intent, "Dataset intent found" if has_dataset_intent else "Add datasets or data/"))

    has_model_cache = any("huggingface" in c.source or "torch" in c.source for c in config.caches) or (proj / "models").exists()
    checks.append(_check("Research model cache", has_model_cache, "Model/cache path found" if has_model_cache else "Add cache mounts or models/"))

    for label, candidates in [
        ("Research experiment notes", ["experiments/evaluation_runs.md", "experiments"]),
        ("Research source notes", ["papers/sources.md", "sources/README.md", "papers"]),
        ("Research graph context", ["graph/context.md", "context/graph.md", "graph"]),
        ("Research reproducibility report", ["reports/reproducibility.md", "outputs/README.md", "reports"]),
    ]:
        ok, detail = _any_exists(proj, candidates)
        checks.append(_check(label, ok, f"Found {detail}" if ok else f"Missing one of: {detail}"))
    return checks


def _deployable_checks(proj, config: ProjectConfig) -> list[dict]:
    checks: list[dict] = []
    has_healthcheck = any(app.healthcheck for app in config.apps)
    checks.append(_check("Deployable app healthcheck", has_healthcheck, "Healthcheck configured" if has_healthcheck else "Add app healthcheck path"))

    for label, candidates in [
        ("Deployable env example", ["configs/env.example", ".env.example"]),
        ("Deployable deployment manifest", ["deploy/deployment.yaml", "deploy/manifest.yaml", "deployment.yaml"]),
        ("Deployable API tester", ["scripts/check_api.py", "tests/test_api_contract.py"]),
        ("Deployable secrets scan", ["scripts/secrets_scan.sh", ".github/workflows/secrets.yml"]),
        ("Deployable logging docs", ["docs/logging.md", "docs/api.md"]),
    ]:
        ok, detail = _any_exists(proj, candidates)
        checks.append(_check(label, ok, f"Found {detail}" if ok else f"Missing one of: {detail}"))
    return checks


def _opensource_checks(proj) -> list[dict]:
    checks: list[dict] = []
    for label, candidates in [
        ("Open-source docs", ["docs/index.md", "docs/README.md"]),
        ("Open-source CI", [".github/workflows/ci.yml", ".github/workflows/tests.yml"]),
        ("Open-source changelog", ["CHANGELOG.md"]),
        ("Open-source release checklist", ["RELEASE.md", "docs/release.md"]),
        ("Open-source package metadata", ["pyproject.toml", "setup.py"]),
    ]:
        ok, detail = _any_exists(proj, candidates)
        checks.append(_check(label, ok, f"Found {detail}" if ok else f"Missing one of: {detail}"))
    return checks
