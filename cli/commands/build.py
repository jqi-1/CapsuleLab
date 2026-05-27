import typer
from rich.console import Console
from backend.services import docker_service, project_service, ssh_service
from backend.services.docker_service import parse_image_tag
from backend.db.repositories import builds, locations

console = Console()


def build(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    location: str = typer.Option(None, "--location", "-l", help="Remote location name"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    project_id = project_service.get_project_id(config.name)
    warnings = project_service.validate(config, project_path)
    for w in warnings:
        console.print(f"[yellow]Warning: {w}[/yellow]")

    image = config.runtime.image or f"{config.name}:dev"
    image_name, tag = parse_image_tag(image)

    if location:
        loc = locations.get_by_name(location)
        if not loc:
            console.print(f"[red]Location '{location}' not found.[/red]")
            raise typer.Exit(1)
        host = loc["host"]
        user = loc.get("user")
        remote_path = ssh_service.remote_project_path(project_path, loc)

        console.print(f"[bold]Building on remote:[/bold] {loc['name']} ({host})")
        console.print(f"[dim]Remote path:[/dim] {remote_path}")
        console.print(f"[dim]Image:[/dim] {image}")
        try:
            result = ssh_service.build(host, remote_path, config.runtime.dockerfile, image_name, tag, user)
            console.print(f"[green]✓[/green] Remote build complete: {image}")
        except ssh_service.SSHError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        return

    if not docker_service.check_docker():
        console.print("[red]Docker is not available. Install Docker and try again.[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Building image:[/bold] {image}")
    console.print(f"[dim]Dockerfile:[/dim] {config.runtime.dockerfile}")
    console.print(f"[dim]Context:[/dim] {project_path}")

    try:
        result, build_logs = docker_service.build_with_logs(project_path, config.runtime.dockerfile, image_name, tag)
        builds.add_log(project_id, result, "success", build_logs)
        try:
            image_info = docker_service.inspect_image(result)
            builds.set_metadata(project_id, result, image_id=image_info.get("Id"), digest=",".join(image_info.get("RepoDigests", []) or []))
        except Exception:
            builds.set_metadata(project_id, result)
        console.print(f"[green]✓[/green] Image built: {result}")
    except docker_service.DockerError as e:
        builds.add_log(project_id, image, "failed", e.stderr or str(e))
        console.print(f"[red]Build failed:[/red] {e.message}")
        if e.stderr:
            console.print(f"\n[bold]Build output:[/bold]")
            console.print(f"[dim]{e.stderr[:2000]}[/dim]")
        if e.suggestion:
            console.print(f"\n[yellow]Suggestion:[/yellow] {e.suggestion}")
        raise typer.Exit(1)
    except Exception as e:
        builds.add_log(project_id, image, "failed", str(e))
        console.print(f"[red]Build failed:[/red] {e}")
        raise typer.Exit(1)
