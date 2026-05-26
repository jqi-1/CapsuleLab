import typer
from rich.console import Console
from backend.services import project_service, docker_service

console = Console()


def shell(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    """Open an interactive shell inside the running project container."""
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    container_name = project_service.get_container_name(config.name)

    if not docker_service.is_running(container_name):
        console.print(f"[red]Container '{container_name}' is not running. Start the project first: cap start[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Opening shell in container '{container_name}'...[/green]")
    docker_service.exec_interactive(container_name)


def exec_cmd(
    command: str = typer.Argument(..., help="Command to run inside the container"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    """Run a command inside the running project container interactively."""
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    container_name = project_service.get_container_name(config.name)

    if not docker_service.is_running(container_name):
        console.print(f"[red]Container '{container_name}' is not running. Start the project first: cap start[/red]")
        raise typer.Exit(1)

    docker_service.exec_command(container_name, command)


def attach(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    """Attach to the running project container's main process."""
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    container_name = project_service.get_container_name(config.name)

    if not docker_service.is_running(container_name):
        console.print(f"[red]Container '{container_name}' is not running. Start the project first: cap start[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Attaching to container '{container_name}'... (Ctrl+P Ctrl+Q to detach)[/green]")
    import subprocess
    try:
        subprocess.run(["docker", "attach", container_name])
    except FileNotFoundError:
        console.print("[red]Docker not found.[/red]")
        raise typer.Exit(1)
