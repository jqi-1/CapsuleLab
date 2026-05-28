import typer
from rich.console import Console

from capsulelab.db.repositories import locations
from capsulelab.services import docker_service, project_service, ssh_service

console = Console()


def logs(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    tail: int = typer.Option(100, "--tail", "-t", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
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
        try:
            output = ssh_service.logs(loc["host"], container_name, tail=tail, user=loc.get("user"))
            console.print(output, end="")
        except Exception as e:
            console.print(f"[red]Failed to get remote logs:[/red] {e}")
            raise typer.Exit(1)
        return

    if not docker_service.container_exists(container_name):
        console.print(f"[red]Container '{container_name}' not found. Start the project first.[/red]")
        raise typer.Exit(1)

    try:
        output = docker_service.logs(container_name, tail=tail, follow=follow)
        console.print(output, end="")
    except Exception as e:
        console.print(f"[red]Failed to get logs:[/red] {e}")
        raise typer.Exit(1)
