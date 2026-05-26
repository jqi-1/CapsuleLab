from backend.models.project import (
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

    return checks
