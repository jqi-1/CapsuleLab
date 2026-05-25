import typer
import webbrowser
import shlex
from rich.console import Console
from rich.table import Table
from backend.services import docker_service, project_service
from backend.db.sqlite import set_app_state, get_app_state, list_app_states

console = Console()
app_cmd = typer.Typer(name="app", help="Manage apps inside a project container", no_args_is_help=True)


def _get_project_context(path: str | None):
    try:
        project_path = project_service.resolve_project_path(path)
        config = project_service.load_config(project_path)
        project_id = project_service.get_project_id(config.name)
        container_name = project_service.get_container_name(config.name)
        return project_path, config, project_id, container_name
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Invalid project config: {e}[/red]")
        raise typer.Exit(1)


@app_cmd.command("list")
def app_list(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, config, project_id, container_name = _get_project_context(path)
    running = docker_service.is_running(container_name)
    states = list_app_states(project_id)

    table = Table(title=f"Apps — {config.name}")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Port")
    table.add_column("Status")
    table.add_column("PID")

    for app_cfg in config.apps:
        state = next((s for s in states if s["app_id"] == app_cfg.id), None)
        status = state["status"] if state else "stopped"
        pid = str(state["pid"]) if state and state.get("pid") else "-"
        if not running:
            status = "container stopped"
            pid = "-"
        table.add_row(app_cfg.id, app_cfg.name, str(app_cfg.port), status, pid)

    console.print(table)


@app_cmd.command("start")
def app_start(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, config, project_id, container_name = _get_project_context(path)
    app_cfg = next((a for a in config.apps if a.id == app_id), None)
    if not app_cfg:
        console.print(f"[red]App '{app_id}' not found in project config.[/red]")
        raise typer.Exit(1)

    if not docker_service.is_running(container_name):
        console.print(f"[red]Container '{container_name}' is not running. Start the project first.[/red]")
        raise typer.Exit(1)

    console.print(f"Starting app '[bold]{app_cfg.name}[/bold]' on port {app_cfg.port}...")
    try:
        docker_service.exec_run(container_name, app_cfg.command, detach=True)
        set_app_state(project_id, app_cfg.id, "running", port=app_cfg.port)
        console.print(f"[green]✓[/green] {app_cfg.name} running at http://localhost:{app_cfg.port}")
    except Exception as e:
        console.print(f"[red]Failed to start app:[/red] {e}")
        set_app_state(project_id, app_cfg.id, "failed", port=app_cfg.port)
        raise typer.Exit(1)


@app_cmd.command("open")
def app_open(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, config, _, _ = _get_project_context(path)
    app_cfg = next((a for a in config.apps if a.id == app_id), None)
    if not app_cfg:
        console.print(f"[red]App '{app_id}' not found in project config.[/red]")
        raise typer.Exit(1)
    url = f"http://localhost:{app_cfg.port}{app_cfg.url_path}"
    console.print(f"Opening [blue]{url}[/blue] in browser...")
    webbrowser.open(url)


@app_cmd.command("stop")
def app_stop(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, config, project_id, container_name = _get_project_context(path)
    app_cfg = next((a for a in config.apps if a.id == app_id), None)
    if not app_cfg:
        console.print(f"[red]App '{app_id}' not found in project config.[/red]")
        raise typer.Exit(1)

    if not docker_service.is_running(container_name):
        console.print(f"[yellow]Container is not running.[/yellow]")
        set_app_state(project_id, app_cfg.id, "stopped")
        return

    state = get_app_state(project_id, app_cfg.id)
    pid = state.get("pid") if state else None

    console.print(f"Stopping app '[bold]{app_cfg.name}[/bold]'...")
    try:
        if pid:
            alive = docker_service.exec_run(container_name, f"kill -0 {pid} 2>/dev/null && echo alive || true")
            if alive.strip() == "alive":
                docker_service.exec_run(container_name, f"kill {pid}")
        first_word = app_cfg.command.split()[0]
        docker_service.exec_run(container_name, f"pkill -f {shlex.quote(first_word)} || true")
        set_app_state(project_id, app_cfg.id, "stopped")
        console.print(f"[green]✓[/green] {app_cfg.name} stopped")
    except Exception as e:
        console.print(f"[red]Failed to stop app:[/red] {e}")
        raise typer.Exit(1)


@app_cmd.command("logs")
def app_logs(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    tail: int = typer.Option(50, "--tail", "-t", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
):
    _, config, _, container_name = _get_project_context(path)
    app_cfg = next((a for a in config.apps if a.id == app_id), None)
    if not app_cfg:
        console.print(f"[red]App '{app_id}' not found in project config.[/red]")
        raise typer.Exit(1)

    if not docker_service.is_running(container_name):
        console.print(f"[red]Container '{container_name}' is not running.[/red]")
        raise typer.Exit(1)

    try:
        output = docker_service.exec_run(
            container_name,
            f"cat /tmp/cap-{app_id}.log 2>&1 || echo 'No app log file found'",
        )
        console.print(output)
    except Exception as e:
        console.print(f"[red]Failed to get app logs:[/red] {e}")
        raise typer.Exit(1)
