import typer
from rich.console import Console
from rich.table import Table

from backend.services import ide_service, project_service

console = Console()
ide_cmd = typer.Typer(name="ide", help="Set up and attach native IDEs", no_args_is_help=True)


def _context(path: str | None) -> tuple[str, str]:
    try:
        project_path = project_service.resolve_project_path(path)
        config = project_service.load_config(project_path)
        return project_path, config.name
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@ide_cmd.command("setup")
def ide_setup(
    ide: str = typer.Argument(..., help="cursor, vscode, windsurf, or all"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    project_path, project_name = _context(path)
    try:
        result = ide_service.setup_ide(project_path, ide, project_name=project_name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Configured {result['ide']} IDE support")
    for file_path in result["files"]:
        console.print(f"  {file_path}")


@ide_cmd.command("instructions")
def ide_instructions(
    ide: str = typer.Argument(..., help="cursor, vscode, or windsurf"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    project_path, project_name = _context(path)
    try:
        result = ide_service.attach_instructions(project_path, ide, project_name=project_name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    table = Table(title=f"{ide} Attach Instructions")
    table.add_column("Step", style="cyan")
    table.add_column("Instruction")
    for idx, instruction in enumerate(result["instructions"], start=1):
        table.add_row(str(idx), instruction)
    console.print(table)
    console.print(f"Container: [bold]{result['container']}[/bold]")
    console.print(f"Workspace: [bold]{result['workspace']}[/bold]")
