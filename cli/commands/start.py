import typer
from pathlib import Path
from rich.console import Console
from backend.services import docker_service, project_service, gpu_service, ssh_service
from backend.db.sqlite import clear_app_states, get_location_by_name

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
        loc = get_location_by_name(location)
        if not loc:
            console.print(f"[red]Location '{location}' not found. Add it first: cap location add {location} --host <host>[/red]")
            raise typer.Exit(1)
        remote_start(project_path, config, container_name, loc)
        return

    if docker_service.is_running(container_name):
        console.print(f"[yellow]Container '{container_name}' is already running.[/yellow]")
        return

    if docker_service.container_exists(container_name):
        info = docker_service.inspect(container_name)
        owned = False
        if info:
            labels = info.get("Config", {}).get("Labels", {}) or {}
            owned = labels.get("com.capsulelab.project") == config.name
        if owned:
            console.print(f"[yellow]Container '{container_name}' already exists for this project. Replacing...[/yellow]")
        else:
            console.print(f"[red]Container '{container_name}' exists but is not owned by this project. Refusing to remove.[/red]")
            console.print("[yellow]Remove it manually: docker rm -f {container_name}[/yellow]")
            raise typer.Exit(1)
        docker_service.stop(container_name)

    image = config.runtime.image or f"{config.name}:dev"

    mounts = []
    for m in config.mounts:
        source = str(Path(project_path) / m.source) if not Path(m.source).is_absolute() else m.source
        mounts.append((source, m.target, m.read_only))
    for c in config.caches:
        c_source = str(Path(c.source).expanduser())
        if Path(c_source).exists():
            mounts.append((c_source, c.target, True))
    for dataset in config.datasets:
        d_source = str(Path(project_path) / dataset.path) if not Path(dataset.path).is_absolute() else dataset.path
        if Path(d_source).exists():
            mounts.append((d_source, dataset.target, dataset.read_only))

    ports = [(a.port, a.port) for a in config.apps if a.port is not None] if config.apps else None

    if config.runtime.gpu:
        if gpu_service.detect_nvidia_smi():
            gpu = True
        else:
            console.print("[yellow]Warning: GPU requested (gpu: true) but nvidia-smi not found. Starting without GPU.[/yellow]")
            gpu = False
    else:
        gpu = False

    if ports:
        used_ports = docker_service.get_used_ports()
        conflicts = [str(p[0]) for p in ports if p[0] in used_ports]
        if conflicts:
            console.print(f"[red]Port conflict detected: port(s) {', '.join(conflicts)} already in use.[/red]")
            console.print("[yellow]Stop the other container or change the port mapping in project.yaml.[/yellow]")
            raise typer.Exit(1)

    dkr = docker_service.check_docker_status()
    if not dkr.available:
        console.print(f"[red]{dkr.error}[/red]")
        raise typer.Exit(1)

    clear_app_states(project_id)

    console.print(f"[bold]Starting container:[/bold] {container_name}")
    console.print(f"[dim]Image:[/dim] {image}")
    console.print(f"[dim]GPU:[/dim] {'enabled' if gpu else 'disabled'}")

    try:
        docker_service.run(
            container_name=container_name,
            image_name=image,
            mounts=mounts,
            env_vars=config.environment or None,
            gpu=gpu,
            ports=ports,
            labels={"com.capsulelab.project": config.name},
        )
        console.print(f"[green]✓[/green] Container started: {container_name}")
        if config.apps:
            console.print("[dim]Start apps with:[/dim]")
            for app_cfg in config.apps:
                console.print(f"  [dim]cap app start {app_cfg.id}[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to start container:[/red] {e}")
        raise typer.Exit(1)


def remote_start(project_path: str, config, container_name: str, loc: dict):
    image = config.runtime.image or f"{config.name}:dev"
    host = loc["host"]
    user = loc.get("user")

    remote_path = ssh_service.remote_project_path(project_path, loc)

    console.print(f"[bold]Starting on remote:[/bold] {loc['name']} ({host})")
    console.print(f"[dim]Remote path:[/dim] {remote_path}")
    console.print(f"[dim]Image:[/dim] {image}")

    gpu = bool(loc["gpu"])

    ports = [f"{a.port}:{a.port}" for a in config.apps if a.port is not None] if config.apps else None
    port_numbers = [a.port for a in config.apps if a.port is not None] if config.apps else []

    check = ssh_service.check_remote_project(
        host,
        remote_path,
        config.runtime.dockerfile,
        ports=port_numbers,
        user=user,
        require_gpu=gpu,
    )
    if not check.docker_available:
        console.print(f"[red]Remote Docker is not available:[/red] {check.error or 'docker info failed'}")
        raise typer.Exit(1)
    if not check.path_exists:
        console.print(f"[red]Remote project path does not exist:[/red] {remote_path}")
        console.print(f"[yellow]Sync it first: cap sync rsync --location {loc['name']}[/yellow]")
        raise typer.Exit(1)
    if check.missing_files:
        console.print(f"[red]Remote project is missing required file(s):[/red] {', '.join(check.missing_files)}")
        console.print(f"[yellow]Sync it again: cap sync rsync --location {loc['name']}[/yellow]")
        raise typer.Exit(1)
    if check.port_conflicts:
        console.print(f"[red]Remote port conflict:[/red] {', '.join(str(p) for p in check.port_conflicts)}")
        console.print("[yellow]Stop the remote process/container using the port or change project.yaml.[/yellow]")
        raise typer.Exit(1)
    if gpu and not check.gpu_available:
        console.print(f"[yellow]{check.error} Starting without --gpus all.[/yellow]")
        gpu = False

    try:
        result = ssh_service.run(host, container_name, image, remote_path, gpu, user, ports)
        console.print(f"[green]✓[/green] Remote container started: {container_name}")
        console.print(f"  [dim]{result}[/dim]")
        if config.apps:
            console.print("[dim]Access apps at:[/dim]")
            for app_cfg in config.apps:
                if app_cfg.port is not None:
                    console.print(f"  [dim]http://{host}:{app_cfg.port}{app_cfg.url_path}[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to start remote container:[/red] {e}")
        raise typer.Exit(1)
