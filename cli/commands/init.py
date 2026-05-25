import typer
import os
from pathlib import Path
from rich.console import Console
from backend.services import project_service
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


def init(
    name: str = typer.Argument(..., help="Project name"),
    template: str = typer.Option("python-basic", "--template", "-t", help="Template name"),
    path: str = typer.Option(None, "--path", "-p", help="Destination directory"),
):
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

    init_db()
    project_id = project_service.get_project_id(name)
    register_project(project_id, name, dest)

    console.print(f"[green]✓[/green] Project [bold]{name}[/bold] created at {dest}")
    console.print(f"  [dim]cd {dest}[/dim]")
    console.print(f"  [dim]cap doctor[/dim]    — check project readiness")
    console.print(f"  [dim]cap build[/dim]     — build container image")
    console.print(f"  [dim]cap start[/dim]     — start project container")
