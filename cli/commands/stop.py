import typer
from rich.console import Console
from backend.services import docker_service, project_service

console = Console()


def stop(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    container_name = project_service.get_container_name(config.name)

    if not docker_service.container_exists(container_name):
        console.print(f"[yellow]Container '{container_name}' does not exist.[/yellow]")
        return

    console.print(f"Stopping container '{container_name}'...")
    try:
        docker_service.stop(container_name)
        console.print(f"[green]✓[/green] Container stopped and removed: {container_name}")
    except Exception as e:
        console.print(f"[red]Failed to stop container:[/red] {e}")
        raise typer.Exit(1)
