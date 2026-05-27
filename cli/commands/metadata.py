import typer
from rich.console import Console
from rich.table import Table

from backend.services import metadata_service

console = Console()
metadata_cmd = typer.Typer(name="metadata", help="Backup and restore local CapsuleLab metadata", no_args_is_help=True)


@metadata_cmd.command("backup")
def backup(
    output: str = typer.Argument(..., help="Backup JSON output path"),
    include_secrets: bool = typer.Option(False, "--include-secrets", help="Include locally stored secret values"),
):
    try:
        result = metadata_service.create_backup(output, include_secrets=include_secrets)
    except Exception as e:
        console.print(f"[red]Backup failed:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Metadata backup written to {result['path']}")
    _print_table_counts(result["tables"], "Backed Up Tables")


@metadata_cmd.command("inspect")
def inspect(path: str = typer.Argument(..., help="Backup JSON path")):
    try:
        result = metadata_service.inspect_backup(path)
    except Exception as e:
        console.print(f"[red]Inspect failed:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"Created: {result['created_at']}")
    console.print(f"Includes secrets: {'yes' if result['include_secrets'] else 'no'}")
    _print_table_counts(result["tables"], "Backup Contents")


@metadata_cmd.command("restore")
def restore(
    path: str = typer.Argument(..., help="Backup JSON path"),
    include_secrets: bool = typer.Option(False, "--include-secrets", help="Restore locally stored secret values from backup"),
):
    try:
        result = metadata_service.restore_backup(path, include_secrets=include_secrets)
    except Exception as e:
        console.print(f"[red]Restore failed:[/red] {e}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Metadata restored from {result['path']}")
    _print_table_counts(result["restored"], "Restored Tables")


def _print_table_counts(counts: dict, title: str):
    table = Table(title=title)
    table.add_column("Table", style="cyan")
    table.add_column("Rows")
    for name, count in counts.items():
        table.add_row(name, str(count))
    console.print(table)
