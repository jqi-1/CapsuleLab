from pathlib import Path

from backend.services import project_service


SUPPORTED_IDES = {"cursor", "vscode", "windsurf"}


def setup_ide(project_path: str, ide: str, project_name: str | None = None) -> dict:
    ide = ide.lower()
    if ide == "all":
        results = [setup_ide(project_path, item, project_name=project_name) for item in sorted(SUPPORTED_IDES)]
        return {
            "ide": "all",
            "files": [path for result in results for path in result["files"]],
            "instructions": attach_instructions(project_path, "cursor", project_name=project_name)["instructions"],
        }
    if ide not in SUPPORTED_IDES:
        raise ValueError(f"Unsupported IDE '{ide}'. Choose one of: {', '.join(sorted(SUPPORTED_IDES))}")
    project = Path(project_path)
    name = project_name or project.name
    if ide == "cursor":
        files = _setup_cursor(project, name)
    elif ide == "vscode":
        files = _setup_vscode(project, name)
    else:
        files = _setup_windsurf(project, name)
    return {
        "ide": ide,
        "files": files,
        "instructions": attach_instructions(project_path, ide, project_name=name)["instructions"],
    }


def attach_instructions(project_path: str, ide: str, project_name: str | None = None) -> dict:
    ide = ide.lower()
    if ide not in SUPPORTED_IDES:
        raise ValueError(f"Unsupported IDE '{ide}'. Choose one of: {', '.join(sorted(SUPPORTED_IDES))}")
    name = project_name or Path(project_path).name
    container_name = project_service.get_container_name(name)
    common = [
        "Start the project container with `cap start`.",
        f"Attach to running container `{container_name}`.",
        "Open `/workspace` inside the container.",
    ]
    if ide == "cursor":
        instructions = [
            *common,
            "Use Cursor command palette: Dev Containers: Attach to Running Container.",
            "The generated `.cursor/rules/ai-workbench/capsulelab.mdc` file gives the agent project/container guidance.",
        ]
    elif ide == "vscode":
        instructions = [
            *common,
            "Use VS Code command palette: Dev Containers: Attach to Running Container.",
            "Install the Dev Containers extension if VS Code prompts for it.",
        ]
    else:
        instructions = [
            *common,
            "Use Windsurf's VS Code-compatible Dev Containers attach flow.",
            "Windsurf is documented as manual attach rather than an AI Workbench Native App launcher.",
        ]
    return {
        "ide": ide,
        "container": container_name,
        "project_path": str(Path(project_path).resolve()),
        "workspace": "/workspace",
        "instructions": instructions,
        "commands": {
            "start_container": "cap start",
            "verify_container": f"docker ps --filter name={container_name}",
            "shell": "cap shell",
        },
    }


def _setup_cursor(project: Path, project_name: str) -> list[str]:
    rules_dir = project / ".cursor" / "rules" / "ai-workbench"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rules_file = rules_dir / "capsulelab.mdc"
    rules_file.write_text(_cursor_rules(project_name))
    return [str(rules_file)]


def _setup_vscode(project: Path, project_name: str) -> list[str]:
    vscode_dir = project / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    extensions = vscode_dir / "extensions.json"
    extensions.write_text(
        """{
  "recommendations": [
    "ms-vscode-remote.remote-containers"
  ]
}
"""
    )
    settings = vscode_dir / "settings.json"
    if not settings.exists():
        settings.write_text(
            """{
  "remote.containers.defaultExtensions": []
}
"""
        )
    return [str(extensions), str(settings)]


def _setup_windsurf(project: Path, project_name: str) -> list[str]:
    rules_dir = project / ".windsurf" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rules_file = rules_dir / "capsulelab.md"
    rules_file.write_text(_agent_rules(project_name, "Windsurf"))
    return [str(rules_file)]


def _cursor_rules(project_name: str) -> str:
    return f"""---
description: CapsuleLab project container guidance
alwaysApply: true
---

# CapsuleLab / AI Workbench-style Container Guidance

This repository is managed as a CapsuleLab project named `{project_name}`.

- Treat the project container as the development boundary.
- Use `cap start` before attaching Cursor to the running container.
- Open `/workspace` in the attached container.
- Do not assume Cursor process sandboxing is active inside containers.
- Treat environment variables and required secrets as sensitive; do not print or persist secret values.
- Changes to `.workbench/project.yaml`, Dockerfile, requirements files, `apt.txt`, `preBuild.bash`, or `postBuild.bash` require a rebuild with `cap build`.
- Use `cap doctor` before long-running work and after environment changes.
- Use `cap project git status` to review agent changes before committing.
"""


def _agent_rules(project_name: str, agent_name: str) -> str:
    return f"""# CapsuleLab {agent_name} Guidance

This repository is a CapsuleLab project named `{project_name}`.

- Start the container with `cap start`.
- Attach {agent_name} to the running container and open `/workspace`.
- Keep host access limited to the mounted project repository.
- Treat secrets and environment variables as sensitive.
- Rebuild with `cap build` after environment-file changes.
- Review changes with `cap project git status` before committing.
"""
