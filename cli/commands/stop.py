import typer
from rich.console import Console
from capsulelab.services import project_service, runtime_service
from capsulelab.db.repositories import locations

console = Console()


def stop(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    location: str = typer.Option(None, "--location", "-l", help="Remote location name"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    container_name = project_service.get_container_name(config.name)

    if location:
        loc = locations.get_by_name(location)
        if not loc:
            console.print(f"[red]Location '{location}' not found.[/red]")
            raise typer.Exit(1)
        adapter = runtime_service.RemoteSSHAdapter(loc, project_path)
        console.print(f"Stopping remote container '[bold]{container_name}[/bold]'...")
    else:
        adapter = runtime_service.LocalDockerAdapter()
        console.print(f"Stopping container '{container_name}'...")

    try:
        runtime = runtime_service.RuntimeManager(adapter)
        result = runtime.stop(config, container_name)
        if result.status == "not_found":
            console.print(f"[yellow]Container '{container_name}' does not exist.[/yellow]")
            return
        console.print(f"[green]✓[/green] Container stopped and removed: {container_name}")
    except runtime_service.RuntimeUnavailable as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except runtime_service.RuntimeConflict as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to stop container:[/red] {e}")
        raise typer.Exit(1)
