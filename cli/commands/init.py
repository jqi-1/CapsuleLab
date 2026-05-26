import typer
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from backend.services import project_service, template_service
from backend.db.sqlite import init_db, register_project

console = Console()
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def _list_templates() -> list[str]:
    templates_dir = TEMPLATES_DIR
    if not templates_dir.exists():
        return []
    return [
        d.name for d in templates_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
        and (d / ".workbench" / "project.yaml").exists()
    ]


def _show_template_table(mode: str | None = None):
    manifest = template_service.load_manifest()
    if mode:
        templates = template_service.list_templates_for_profile(mode)
    else:
        templates = template_service.list_maintained_templates()
    table = Table(title=f"Available templates{' for ' + mode if mode else ''}")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("GPU", style="yellow")
    table.add_column("Mode", style="magenta")
    for name in sorted(templates, key=lambda t: template_service.MAINTAINED_TEMPLATES.index(t) if t in template_service.MAINTAINED_TEMPLATES else 99):
        meta = manifest.get(name, {})
        table.add_row(
            name,
            meta.get("description", ""),
            "✓" if meta.get("gpu") else "—",
            meta.get("mode", "research"),
        )
    return table


def init(
    name: str = typer.Argument(None, help="Project name"),
    template: str = typer.Option("python-basic", "--template", "-t", help="Template name"),
    path: str = typer.Option(None, "--path", "-p", help="Destination directory"),
    mode: str = typer.Option(None, "--mode", "-m", help="Project profile: research, deployable, opensource"),
    list_templates: bool = typer.Option(False, "--list-templates", "-l", help="List available templates"),
):
    if list_templates:
        console.print(_show_template_table(mode))
        raise typer.Exit(0)
    if not name:
        console.print("[red]Project name is required[/red]")
        raise typer.Exit(1)

    template_path = TEMPLATES_DIR / template
    if not template_path.exists():
        available = _list_templates()
        console.print(f"[red]Template '{template}' not found.[/red]")
        if available:
            console.print(f"Available templates: {', '.join(available)}")
        raise typer.Exit(1)

    dest = path or os.path.join(os.getcwd(), name)
    try:
        project_service.create_from_template(name, str(template_path), dest)
    except FileExistsError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to create project: {e}[/red]")
        raise typer.Exit(1)

    if mode:
        config_path = Path(dest) / ".workbench" / "project.yaml"
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                cfg_data = yaml.safe_load(f)
            cfg_data["mode"] = mode
            from backend.models.project import default_presets, ProjectMode
            pm = ProjectMode(mode) if mode in ("research", "deployable", "opensource") else None
            if pm:
                cfg_data["presets"] = default_presets(pm)
            with open(config_path, "w") as f:
                yaml.dump(cfg_data, f, default_flow_style=False)

    init_db()
    project_id = project_service.get_project_id(name)
    register_project(project_id, name, dest)

    console.print(f"[green]✓[/green] Project [bold]{name}[/bold] created at {dest}")
    console.print(f"  [dim]cd {dest}[/dim]")
    console.print(f"  [dim]cap doctor[/dim]    — check project readiness")
    console.print(f"  [dim]cap build[/dim]     — build container image")
    console.print(f"  [dim]cap start[/dim]     — start project container")
