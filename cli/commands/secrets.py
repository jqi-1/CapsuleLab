import getpass

import typer
from rich.console import Console
from rich.table import Table

from backend.db.sqlite import init_db
from backend.services import project_service, secrets_service

console = Console()
secrets_cmd = typer.Typer(name="secrets", help="Manage local project secrets without writing values to the repo", no_args_is_help=True)


def _project(path: str | None):
    project_path = project_service.resolve_project_path(path)
    config = project_service.load_config(project_path)
    return project_path, config, project_service.get_project_id(config.name)


@secrets_cmd.command("set")
def secrets_set(
    name: str = typer.Argument(..., help="Secret name"),
    value: str | None = typer.Option(None, "--value", "-v", help="Secret value. Omit to prompt."),
    location: str | None = typer.Option(None, "--location", "-l", help="Optional location-specific value"),
    path: str | None = typer.Option(None, "--path", "-p", help="Project directory"),
):
    init_db()
    _, _, project_id = _project(path)
    secret_value = value if value is not None else getpass.getpass(f"{name}: ")
    secrets_service.set_secret(project_id, name, secret_value, location)
    console.print(f"[green]✓[/green] Secret {name} set" + (f" for {location}" if location else ""))


@secrets_cmd.command("list")
def secrets_list(path: str | None = typer.Option(None, "--path", "-p", help="Project directory")):
    _, _, project_id = _project(path)
    rows = secrets_service.list_secret_presence(project_id)
    table = Table(title="Secrets")
    table.add_column("Name", style="cyan")
    table.add_column("Location")
    table.add_column("Updated")
    for row in rows:
        table.add_row(row["name"], row["location"] or "default", row["updated_at"])
    console.print(table)


@secrets_cmd.command("remove")
def secrets_remove(
    name: str = typer.Argument(..., help="Secret name"),
    location: str | None = typer.Option(None, "--location", "-l", help="Optional location-specific value"),
    path: str | None = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, _, project_id = _project(path)
    secrets_service.remove_secret(project_id, name, location)
    console.print(f"[green]✓[/green] Secret {name} removed" + (f" for {location}" if location else ""))
