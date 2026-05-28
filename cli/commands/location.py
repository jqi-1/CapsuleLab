import typer
from rich.console import Console
from rich.table import Table

from capsulelab.db.repositories import locations
from capsulelab.db.sqlite import init_db
from capsulelab.services import ssh_service

console = Console()
location_cmd = typer.Typer(name="location", help="Manage remote execution locations", no_args_is_help=True)


def _get_location_id(name: str) -> str:
    return f"loc-{name.replace('_', '-').replace(' ', '-').lower()}"


@location_cmd.command("add")
def location_add(
    name: str = typer.Argument(..., help="Location name"),
    host: str = typer.Option(..., "--host", "-h", help="Remote host address"),
    user: str = typer.Option(None, "--user", "-u", help="SSH user"),
    project_root: str = typer.Option(None, "--project-root", "-p", help="Remote project root"),
    gpu: bool = typer.Option(False, "--gpu", help="GPU available on remote"),
):
    init_db()
    location_id = _get_location_id(name)
    locations.register(location_id, name, "ssh", host, user, project_root, "docker", gpu)
    loc = locations.get_by_name(name)
    tunnel = ssh_service.tunnel_info(loc)

    console.print(f"[green]✓[/green] Location [bold]{name}[/bold] added")
    console.print(f"  Host: {host}")
    console.print(f"  User: {user or '(default)'}")
    console.print(f"  GPU: {'yes' if gpu else 'no'}")
    console.print(f"  Proxy URL: {tunnel['proxy_url']}")
    console.print(f"  Service URL: {tunnel['service_url']}")

    console.print("\n[dim]Checking remote connectivity...[/dim]")
    docker_ok = ssh_service.check_docker(host, user)
    if docker_ok:
        console.print("  [green]✓[/green] Docker available on remote")
    else:
        console.print("  [red]✗[/red] Docker not reachable on remote")

    if gpu:
        gpu_ok = ssh_service.check_gpu(host, user)
        if gpu_ok:
            console.print("  [green]✓[/green] GPU detected on remote")
        else:
            console.print("  [yellow]⚠[/yellow] GPU not detected (nvidia-smi)")


@location_cmd.command("list")
def location_list():
    all_locations = locations.list()
    if not all_locations:
        console.print("[yellow]No locations configured.[/yellow]")
        return

    table = Table(title="Remote Locations")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Host")
    table.add_column("User")
    table.add_column("GPU")
    table.add_column("Project Root")
    table.add_column("Proxy")
    table.add_column("Service")

    for loc in all_locations:
        tunnel = ssh_service.tunnel_info(loc)
        table.add_row(
            loc["name"],
            loc["type"],
            loc["host"] or "-",
            loc["user"] or "-",
            "[green]yes[/green]" if loc["gpu"] else "no",
            loc["project_root"] or "-",
            tunnel["proxy_url"],
            tunnel["service_url"],
        )
    console.print(table)


@location_cmd.command("tunnel")
def location_tunnel(
    name: str = typer.Argument(..., help="Location name"),
):
    loc = locations.get_by_name(name)
    if not loc:
        console.print(f"[red]Location '{name}' not found.[/red]")
        raise typer.Exit(1)
    tunnel = ssh_service.tunnel_info(loc)
    table = Table(title=f"Tunnel — {name}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Proxy URL", tunnel["proxy_url"])
    table.add_row("Service URL", tunnel["service_url"])
    table.add_row("Command", tunnel["command_text"])
    console.print(table)


@location_cmd.command("override")
def location_override(
    name: str = typer.Argument(..., help="Location name"),
    override_type: str = typer.Option(..., "--type", "-t", help="Override type: dataset, cache, secret"),
    logical_name: str = typer.Option(..., "--name", "-n", help="Logical name of the dataset/cache/secret"),
    value: str = typer.Option("", "--value", "-v", help="Override value (path or location)"),
    remove: bool = typer.Option(False, "--remove", "-r", help="Remove the override instead of setting it"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all overrides for this location"),
):
    loc = locations.get_by_name(name)
    if not loc:
        console.print(f"[red]Location '{name}' not found.[/red]")
        raise typer.Exit(1)

    if list_all:
        overrides = locations.list_overrides(loc["id"])
        if not overrides:
            console.print("[yellow]No overrides for this location.[/yellow]")
            return
        table = Table(title=f"Location Overrides — {name}")
        table.add_column("Type", style="cyan")
        table.add_column("Logical Name")
        table.add_column("Value")
        for o in overrides:
            table.add_row(o["override_type"], o["logical_name"], o["value"])
        console.print(table)
        return

    if remove:
        locations.remove_override(loc["id"], override_type, logical_name)
        console.print(f"[green]✓[/green] Removed {override_type} override '{logical_name}' from '{name}'")
        return

    if not value:
        console.print("[red]--value is required when setting an override.[/red]")
        raise typer.Exit(1)

    locations.set_override(loc["id"], override_type, logical_name, value)
    console.print(f"[green]✓[/green] Set {override_type} override '{logical_name}' → {value} on '{name}'")


@location_cmd.command("remove")
def location_remove(
    name: str = typer.Argument(..., help="Location name to remove"),
):
    loc = locations.get_by_name(name)
    if not loc:
        console.print(f"[red]Location '{name}' not found.[/red]")
        raise typer.Exit(1)
    locations.remove(loc["id"])
    console.print(f"[green]✓[/green] Location '[bold]{name}[/bold]' removed")


@location_cmd.command("check")
def location_check(
    name: str = typer.Argument(..., help="Location name"),
    path: str = typer.Option(
        None, "--path", "-p", help="Optional local project directory to check remote project path"
    ),
):
    loc = locations.get_by_name(name)
    if not loc:
        console.print(f"[red]Location '{name}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"Checking location [bold]{loc['name']}[/bold] ({loc['host']})...")

    from rich.table import Table

    table = Table(show_header=False, box=None)
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail")

    status = ssh_service.check_status(loc["host"], loc["user"], loc.get("project_root"))

    reachable_str = "[green]✓[/green] Reachable" if status.reachable else "[red]✗[/red] Unreachable"
    table.add_row("SSH", reachable_str, "" if status.reachable else status.error)

    if status.reachable:
        if status.docker_available:
            table.add_row("Docker", "[green]✓[/green] Available", f"version {status.docker_version}")
        else:
            table.add_row("Docker", "[red]✗[/red] Not available", status.error or "")

        if status.gpu_available:
            table.add_row("GPU", "[green]✓[/green] Detected", status.gpu_name)
        elif loc["gpu"]:
            table.add_row("GPU", "[yellow]⚠[/yellow] Not detected", "nvidia-smi not found (configured as GPU location)")
        else:
            table.add_row("GPU", "[dim]–[/dim] Not checked", "GPU not configured for this location")

        if loc.get("project_root"):
            table.add_row(
                "Project root",
                "[green]✓[/green] Found" if status.project_path_exists else "[yellow]⚠[/yellow] Missing",
                loc["project_root"],
            )
        if status.disk_total_gb:
            table.add_row(
                "Disk",
                f"{status.disk_used_percent}% used",
                f"{status.disk_free_gb} GB free of {status.disk_total_gb} GB",
            )

    if path and status.reachable:
        from capsulelab.services import project_service

        try:
            project_path = project_service.resolve_project_path(path)
            config = project_service.load_config(project_path)
            remote_path = ssh_service.remote_project_path(project_path, loc)
            project_check = ssh_service.check_remote_project(
                loc["host"],
                remote_path,
                config.runtime.dockerfile,
                ports=[app.port for app in config.apps if app.port is not None],
                user=loc["user"],
                require_gpu=bool(loc["gpu"]),
            )
            table.add_row(
                "Remote project path",
                "[green]✓[/green] Found" if project_check.path_exists else "[red]✗[/red] Missing",
                remote_path,
            )
            table.add_row(
                "Remote required files",
                "[green]✓[/green] Present" if not project_check.missing_files else "[red]✗[/red] Missing",
                ", ".join(project_check.missing_files)
                if project_check.missing_files
                else ".workbench/project.yaml and Dockerfile present",
            )
            table.add_row(
                "Remote app ports",
                "[green]✓[/green] Free" if not project_check.port_conflicts else "[red]✗[/red] In use",
                ", ".join(str(p) for p in project_check.port_conflicts)
                if project_check.port_conflicts
                else "No conflicts detected",
            )
        except Exception as e:
            table.add_row("Remote project path", "[red]✗[/red] Check failed", str(e))

    console.print(table)
