import typer
from rich.console import Console
from rich.table import Table

from backend.services import settings_service

console = Console()
settings_cmd = typer.Typer(name="settings", help="Manage local CapsuleLab preferences", no_args_is_help=True)


@settings_cmd.command("list")
def settings_list():
    values = settings_service.list_settings()
    table = Table(title="CapsuleLab Settings")
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    for key, value in values.items():
        table.add_row(key, str(value))
    console.print(table)


@settings_cmd.command("set")
def settings_set(
    key: str = typer.Argument(..., help="Setting key"),
    value: str = typer.Argument(..., help="Setting value"),
):
    try:
        result = settings_service.set_setting(key, value)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] {result['key']} = {result['value']}")


@settings_cmd.command("unset")
def settings_unset(key: str = typer.Argument(..., help="Setting key")):
    removed = settings_service.remove_setting(key)
    console.print(f"[green]✓[/green] Removed {key}" if removed else f"[yellow]No value stored for {key}[/yellow]")
