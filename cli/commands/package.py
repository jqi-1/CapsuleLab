import typer
from rich.console import Console
from capsulelab.services import package_service, project_service

console = Console()
package_cmd = typer.Typer(name="package", help="Export/import project capsules", no_args_is_help=True)


@package_cmd.command("export")
def package_export(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    output: str = typer.Option(None, "--output", "-o", help="Output path for the capsule archive"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    config = project_service.load_config(project_path)
    project_id = project_service.get_project_id(config.name)
    try:
        result = package_service.export_project(project_id, output)
        console.print(f"[green]✓[/green] Capsule exported to [bold]{result}[/bold]")
        console.print(f"  To import: cap package import {result}")
    except Exception as e:
        console.print(f"[red]Export failed:[/red] {e}")
        raise typer.Exit(1)


@package_cmd.command("import")
def package_import(
    capsule: str = typer.Argument(..., help="Path to capsule .tar.gz archive"),
    dest: str = typer.Option(None, "--dest", "-d", help="Destination directory"),
):
    try:
        result = package_service.import_project(capsule, dest_dir=dest)
        console.print(f"[green]✓[/green] Imported capsule as [bold]{result['name']}[/bold]")
        console.print(f"  Path: {result['path']}")
        if "manifest" in result and result["manifest"]:
            m = result["manifest"]
            console.print(f"  Exported: {m.get('exported_at', 'unknown')}")
            console.print(f"  Description: {m.get('project_description', '-')}")
    except Exception as e:
        console.print(f"[red]Import failed:[/red] {e}")
        raise typer.Exit(1)
