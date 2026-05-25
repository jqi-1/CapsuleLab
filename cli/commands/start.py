import typer
from pathlib import Path
from rich.console import Console
from backend.services import docker_service, project_service, gpu_service

console = Console()


def start(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = project_service.load_config(project_path)
    container_name = project_service.get_container_name(config.name)

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

    ports = [(a.port, a.port) for a in config.apps] if config.apps else None

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
        if config.apps:
            console.print("[dim]Start apps with:[/dim]")
            for app_cfg in config.apps:
                console.print(f"  [dim]cap app start {app_cfg.id}[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to start container:[/red] {e}")
        raise typer.Exit(1)
