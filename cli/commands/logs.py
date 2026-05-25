import typer
from rich.console import Console
from backend.services import docker_service, project_service

console = Console()


def logs(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    tail: int = typer.Option(100, "--tail", "-t", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    container_name = project_service.get_container_name(config.name)

    if not docker_service.container_exists(container_name):
        console.print(f"[red]Container '{container_name}' not found. Start the project first.[/red]")
        raise typer.Exit(1)

    try:
        output = docker_service.logs(container_name, tail=tail, follow=follow)
        console.print(output, end="")
    except Exception as e:
        console.print(f"[red]Failed to get logs:[/red] {e}")
        raise typer.Exit(1)
