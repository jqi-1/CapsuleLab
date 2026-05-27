import typer
from rich.console import Console
from capsulelab.services import project_service, ssh_service
from capsulelab.db.repositories import locations

console = Console()
sync_cmd = typer.Typer(name="sync", help="Sync project to a remote location", no_args_is_help=True)


@sync_cmd.command("rsync")
def sync_rsync(
    location: str = typer.Option(..., "--location", "-l", help="Remote location name"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be synced"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    loc = locations.get_by_name(location)
    if not loc:
        console.print(f"[red]Location '{location}' not found.[/red]")
        raise typer.Exit(1)

    host = loc["host"]
    user = loc.get("user")
    remote_path = ssh_service.remote_project_path(project_path, loc)

    console.print(f"[bold]Syncing project to:[/bold] {loc['name']} ({host})")
    console.print(f"  [dim]Local:[/dim]  {project_path}")
    console.print(f"  [dim]Remote:[/dim] {remote_path}")

    status = ssh_service.check_status(host, user)
    if not status.reachable:
        console.print(f"[red]Location not reachable: {status.error}[/red]")
        raise typer.Exit(1)

    if dry_run:
        console.print("\n[yellow]Dry run — no files transferred.[/yellow]")
        console.print(f"Would sync: {project_path}/ -> {host}:{remote_path}/")
        return

    try:
        result = ssh_service.sync_project(project_path, host, remote_path, user)
        console.print(f"[green]✓[/green] Project synced to {host}:{remote_path}")
        # Extract line count from rsync output
        lines = [l for l in result.split("\n") if l.strip() and not l.startswith(".")]
        console.print(f"  [dim]Transferred: {len(lines)} items[/dim]")
    except ssh_service.SSHError as e:
        console.print(f"[red]Sync failed:[/red] {e}")
        raise typer.Exit(1)
