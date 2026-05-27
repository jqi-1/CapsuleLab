import typer
import webbrowser
from rich.console import Console
from rich.table import Table
from backend.services import docker_service, project_service, app_service
from backend.db.repositories import apps

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


def _get_app_config(config, app_id: str):
    try:
        return app_service.get_app_config(config, app_id)
    except app_service.AppError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@app_cmd.command("list")
def app_list(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, config, project_id, container_name = _get_project_context(path)
    running = docker_service.is_running(container_name)

    table = Table(title=f"Apps — {config.name}")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Port")
    table.add_column("Status")
    table.add_column("Health")
    table.add_column("PID")
    table.add_column("Proxy URL")

    for app_cfg in config.apps:
        status = app_service.get_app_status(project_id, app_cfg, container_name)
        if not running:
            status_str = "container stopped"
            health_str = "-"
            pid_str = "-"
        elif status["alive"] is True:
            status_str = "running"
            health_str = "[green]alive[/green]"
            pid_str = str(status["pid"])
        elif status["alive"] is False:
            status_str = status["state"]
            health_str = "[red]dead[/red]"
            pid_str = str(status["pid"]) if status["pid"] else "-"
        else:
            status_str = status["state"]
            health_str = "-"
            pid_str = str(status["pid"]) if status["pid"] else "-"
        table.add_row(app_cfg.id, app_cfg.name, str(app_cfg.port), status_str, health_str, pid_str, status["proxy_url"] or "-")

    console.print(table)


@app_cmd.command("start")
def app_start(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, config, project_id, container_name = _get_project_context(path)
    app_cfg = _get_app_config(config, app_id)

    try:
        result = app_service.start_app(project_id, app_cfg, container_name)
        if result["status"] == "already_running":
            console.print(f"[yellow]App '{app_cfg.name}' is already running (PID {result['pid']}).[/yellow]")
            if result.get("proxy_url"):
                console.print(f"Proxy URL: [blue]{result['proxy_url']}[/blue]")
            return
        console.print(f"[green]✓[/green] {app_cfg.name} running at {result['url']} (PID {result['pid']})")
        if result.get("proxy_url"):
            console.print(f"Proxy URL: [blue]{result['proxy_url']}[/blue]")
    except app_service.AppError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@app_cmd.command("open")
def app_open(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    proxy: bool = typer.Option(False, "--proxy", help="Open the stable local proxy URL"),
):
    _, config, project_id, _ = _get_project_context(path)
    app_cfg = _get_app_config(config, app_id)
    url = app_service.get_proxy_app_url(project_id, app_cfg) if proxy else app_service.get_app_url(app_cfg)
    console.print(f"Opening [blue]{url}[/blue] in browser...")
    webbrowser.open(url)


@app_cmd.command("stop")
def app_stop(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, config, project_id, container_name = _get_project_context(path)
    app_cfg = _get_app_config(config, app_id)

    try:
        app_service.stop_app(project_id, app_cfg, container_name)
        console.print(f"[green]✓[/green] {app_cfg.name} stopped")
    except app_service.AppError as e:
        console.print(f"[red]Failed to stop app:[/red] {e}")
        raise typer.Exit(1)


@app_cmd.command("logs")
def app_logs(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    tail: int = typer.Option(50, "--tail", "-t", help="Number of lines to show"),
):
    _, config, _, container_name = _get_project_context(path)
    app_cfg = _get_app_config(config, app_id)

    try:
        output = app_service.get_app_logs(container_name, app_cfg.id, tail=tail)
        console.print(output)
    except app_service.AppError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@app_cmd.command("health")
def app_health(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, config, project_id, container_name = _get_project_context(path)
    app_cfg = _get_app_config(config, app_id)

    status = app_service.get_app_status(project_id, app_cfg, container_name)
    if not status["container_running"]:
        console.print(f"[red]Container '{container_name}' is not running.[/red]")
        raise typer.Exit(1)

    if not status["pid"]:
        console.print(f"[yellow]No runtime state for '{app_id}'. Start the app first.[/yellow]")
        return

    if status["alive"]:
        console.print(f"[green]✓[/green] {app_cfg.name} (PID {status['pid']}) is [green]alive[/green]")
    else:
        console.print(f"[red]✗[/red] {app_cfg.name} (PID {status['pid']}) is [red]dead[/red]")
        if status["state"] == "running":
            apps.set_state(project_id, app_cfg.id, "failed", pid=status["pid"])


@app_cmd.command("share")
def app_share(
    app_id: str = typer.Argument(..., help="App ID (e.g. jupyter)"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    public_base_url: str = typer.Option("http://localhost:10000", "--base-url", help="Public proxy base URL"),
    hours: int = typer.Option(48, "--hours", help="Share expiry in hours"),
):
    _, config, project_id, _ = _get_project_context(path)
    app_cfg = _get_app_config(config, app_id)
    try:
        share = app_service.create_share_url(project_id, app_cfg, public_base_url, hours)
    except app_service.AppError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Share URL: [blue]{share['url']}[/blue]")
    console.print(f"Expires: {share['expires_at']}")


@app_cmd.command("shares")
def app_shares(
    app_id: str | None = typer.Argument(None, help="Optional app ID"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    _, _, project_id, _ = _get_project_context(path)
    shares = app_service.list_share_urls(project_id, app_id=app_id)
    table = Table(title="App Shares")
    table.add_column("App", style="cyan")
    table.add_column("URL")
    table.add_column("Expires")
    table.add_column("Expired")
    table.add_column("Token")
    for share in shares:
        table.add_row(
            share["app_id"],
            share["url"],
            share["expires_at"],
            "yes" if share["expired"] else "no",
            share["token"],
        )
    console.print(table)


@app_cmd.command("revoke-share")
def app_revoke_share(
    token: str = typer.Argument(..., help="Share token"),
):
    if app_service.revoke_share_url(token):
        console.print(f"[green]✓[/green] Revoked share {token}")
    else:
        console.print(f"[red]Share not found:[/red] {token}")
        raise typer.Exit(1)
