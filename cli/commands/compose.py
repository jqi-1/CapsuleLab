from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from capsulelab.services import compose_service, project_service

console = Console()
compose_cmd = typer.Typer(name="compose", help="Manage Docker Compose services", no_args_is_help=True)


def _get_context(path: str | None):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    compose_file = compose_service.find_compose_file(project_path)
    if not compose_file:
        console.print("[red]No docker-compose.yaml or compose.yaml found in project.[/red]")
        console.print("[yellow]Create a docker-compose.yaml file to use compose commands.[/yellow]")
        raise typer.Exit(1)

    binary = compose_service.compose_binary()
    if not binary:
        console.print("[red]Docker Compose not found. Install docker-compose or Docker with Compose v2.[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    return project_path, compose_file, binary, config


@compose_cmd.command("up")
def compose_up(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    detach: bool = typer.Option(True, "--detach", "-d", help="Run in background"),
    build: bool = typer.Option(False, "--build", help="Rebuild images before starting"),
    profile: list[str] = typer.Option(None, "--profile", help="Compose profile to enable"),
):
    project_path, compose_file, binary, config = _get_context(path)
    console.print(f"[bold]Starting Compose services[/bold] in {Path(project_path).name}")
    console.print(f"[dim]Compose file:[/dim] {compose_file.name}")

    try:
        compose_service.up(project_path, build=build, detach=detach, profiles=profile or [])
        if detach:
            console.print("[green]✓[/green] Compose services started")
            console.print("[dim]View logs: cap compose logs[/dim]")
            console.print("[dim]Stop: cap compose down[/dim]")
    except Exception as e:
        console.print(f"[red]Compose up failed:[/red] {e}")
        raise typer.Exit(1)


@compose_cmd.command("down")
def compose_down(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    volumes: bool = typer.Option(False, "--volumes", "-v", help="Remove volumes"),
):
    project_path, compose_file, binary, config = _get_context(path)
    console.print("[bold]Stopping Compose services...[/bold]")

    try:
        compose_service.down(project_path, volumes=volumes)
        console.print("[green]✓[/green] Compose services stopped")
    except Exception as e:
        console.print(f"[red]Compose down failed:[/red] {e}")
        raise typer.Exit(1)


@compose_cmd.command("logs")
def compose_logs(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    service: str = typer.Option(None, "--service", "-s", help="Show logs for a specific service"),
    tail: int = typer.Option(50, "--tail", "-t", help="Number of lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow logs"),
):
    project_path, compose_file, binary, config = _get_context(path)

    try:
        if follow:
            import subprocess

            args = [*binary.split(), "-f", str(compose_file), "logs", "--tail", str(tail), "--follow"]
            if service:
                args.append(service)
            subprocess.run(args, cwd=project_path)
        else:
            console.print(compose_service.logs(project_path, service=service, tail=tail))
    except Exception as e:
        console.print(f"[red]Failed to get compose logs:[/red] {e}")
        raise typer.Exit(1)


@compose_cmd.command("ps")
def compose_ps(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    project_path, compose_file, binary, config = _get_context(path)

    try:
        services = compose_service.ps(project_path)
        table = Table(title="Compose Services")
        table.add_column("Name", style="cyan")
        table.add_column("Service")
        table.add_column("State")
        table.add_column("Ports")
        for service_info in services:
            table.add_row(
                str(service_info.get("name") or "-"),
                str(service_info.get("service") or "-"),
                str(service_info.get("state") or "-"),
                str(service_info.get("ports") or "-"),
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Failed to get compose status:[/red] {e}")
        raise typer.Exit(1)


@compose_cmd.command("detect")
def compose_detect(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    compose_file = compose_service.find_compose_file(project_path)
    binary = compose_service.compose_binary()

    table = Table(title="Compose Detection")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail")

    if binary:
        table.add_row("Compose CLI", "[green]✓[/green]", binary)
    else:
        table.add_row("Compose CLI", "[red]✗[/red]", "Not found")

    if compose_file:
        table.add_row("Compose file", "[green]✓[/green]", compose_file.name)
    else:
        table.add_row("Compose file", "[yellow]–[/yellow]", "Not found")

    console.print(table)


@compose_cmd.command("inspect")
def compose_inspect(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    project_path, compose_file, binary, config = _get_context(path)
    status = compose_service.status(project_path)

    table = Table(title=f"Compose Definition — {compose_file.name}")
    table.add_column("Service", style="cyan")
    table.add_column("Profiles")
    table.add_column("Ports")
    table.add_column("Web")
    table.add_column("Health")
    table.add_column("Depends On")
    table.add_column("URLs")
    for service in status["definitions"]:
        ports = ", ".join(str(port.get("raw")) for port in service["ports"]) or "-"
        table.add_row(
            service["service"],
            ", ".join(service["profiles"]) or "-",
            ports,
            "yes" if service["web_access"] else "no",
            "yes" if service["healthcheck"] else "no",
            ", ".join(service["depends_on"]) or "-",
            ", ".join(service["urls"]) or "-",
        )
    console.print(table)

    if status["profiles"]:
        console.print(f"Profiles: {', '.join(status['profiles'])}")
    for finding in status["findings"]:
        console.print(f"[yellow]{finding['severity']}[/yellow] {finding['label']}: {finding['detail']}")
