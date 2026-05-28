import typer
from rich.console import Console

from capsulelab.db.repositories import apps, locations
from capsulelab.services import project_service, runtime_service

console = Console()


def start(
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
    container_name = project_service.get_container_name(config.name)

    if location:
        loc = locations.get_by_name(location)
        if not loc:
            console.print(
                f"[red]Location '{location}' not found. Add it first: cap location add {location} --host <host>[/red]"
            )
            raise typer.Exit(1)
        adapter = runtime_service.RemoteSSHAdapter(loc, project_path)
        console.print(f"[bold]Starting on remote:[/bold] {loc['name']} ({loc['host']})")
        console.print(f"[dim]Remote path:[/dim] {adapter.remote_path}")
    else:
        adapter = runtime_service.LocalDockerAdapter()

    console.print(f"[bold]Starting container:[/bold] {container_name}")
    try:
        runtime = runtime_service.RuntimeManager(adapter)
        result = runtime.start(project_path, config, container_name)
        if result.status == "already_running":
            console.print(f"[yellow]Container '{container_name}' is already running.[/yellow]")
            return

        apps.clear_states(project_id)
        console.print(f"[dim]Image:[/dim] {result.image}")
        console.print(f"[dim]GPU:[/dim] {'enabled' if result.gpu else 'disabled'}")
        console.print(f"[green]✓[/green] Container started: {container_name}")
        if result.detail:
            console.print(f"  [dim]{result.detail}[/dim]")
        if config.apps:
            console.print("[dim]Access apps at:[/dim]" if location else "[dim]Start apps with:[/dim]")
            for app_cfg in config.apps:
                if location and app_cfg.port is not None:
                    console.print(f"  [dim]http://{loc['host']}:{app_cfg.port}{app_cfg.url_path}[/dim]")
                else:
                    console.print(f"  [dim]cap app start {app_cfg.id}[/dim]")
    except runtime_service.RuntimeUnavailable as e:
        console.print(f"[red]{e}[/red]")
        if location:
            console.print(f"[yellow]Sync it first: cap sync rsync --location {location}[/yellow]")
        raise typer.Exit(1)
    except runtime_service.RuntimeConflict as e:
        console.print(f"[red]{e}[/red]")
        console.print("[yellow]Stop the other container or change the port mapping in project.yaml.[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to start container:[/red] {e}")
        raise typer.Exit(1)
