import typer
from pathlib import Path
from rich.console import Console
from backend.services import docker_service, project_service

console = Console()


def build(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    warnings = project_service.validate(config, project_path)
    for w in warnings:
        console.print(f"[yellow]Warning: {w}[/yellow]")

    if not docker_service.check_docker():
        console.print("[red]Docker is not available. Install Docker and try again.[/red]")
        raise typer.Exit(1)

    image = config.runtime.image or f"{config.name}:dev"
    if ":" in image:
        image_name, tag = image.rsplit(":", 1)
    else:
        image_name, tag = image, "dev"

    console.print(f"[bold]Building image:[/bold] {image}")
    console.print(f"[dim]Dockerfile:[/dim] {config.runtime.dockerfile}")
    console.print(f"[dim]Context:[/dim] {project_path}")

    try:
        result = docker_service.build(project_path, config.runtime.dockerfile, image_name, tag)
        console.print(f"[green]✓[/green] Image built: {result}")
    except Exception as e:
        console.print(f"[red]Build failed:[/red] {e}")
        raise typer.Exit(1)
