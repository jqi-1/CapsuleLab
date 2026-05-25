import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from backend.services import docker_service, gpu_service, project_service

console = Console()


def doctor(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
):
    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)

    checks: list[tuple[str, bool, str]] = []

    config_path = Path(project_path) / ".workbench" / "project.yaml"
    if config_path.exists():
        checks.append(("Config file (.workbench/project.yaml)", True, "Found"))
        try:
            config = project_service.load_config(project_path)
            checks.append(("Config is valid YAML", True, f"Project: {config.name}"))
            for warning in project_service.validate(config, project_path):
                checks.append((f"Validation: {warning}", False, "Warning"))
        except Exception as e:
            checks.append(("Config is valid YAML", False, str(e)))
    else:
        checks.append(("Config file (.workbench/project.yaml)", False, "Missing"))

    df_path = Path(project_path) / "Dockerfile"
    checks.append(("Dockerfile", df_path.exists(), "Found" if df_path.exists() else "Missing"))

    readme = Path(project_path) / "README.md"
    checks.append(("README.md", readme.exists(), "Found" if readme.exists() else "Missing"))

    docker_ok = docker_service.check_docker()
    checks.append(("Docker installed", docker_ok, "Available" if docker_ok else "Not found"))

    if docker_ok:
        containers = docker_service.ps()
        checks.append(("Docker daemon responding", True, f"{len(containers)} container(s) running"))

    gpu_info = gpu_service.get_gpu_info()
    if gpu_info.available:
        checks.append(("GPU detected", True, f"{gpu_info.name} ({gpu_info.vram_mb} MB)"))
        docker_gpu = gpu_service.docker_gpu_available()
        checks.append(("Docker GPU support", docker_gpu, "Available" if docker_gpu else "Not configured"))
    else:
        checks.append(("GPU detected", False, "Not found — running in CPU mode"))

    table = Table(title=f"Doctor Report — {Path(project_path).name}")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Detail")

    all_ok = True
    for label, ok, detail in checks:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        if not ok:
            all_ok = False
        table.add_row(label, status, detail)

    console.print(table)

    if all_ok:
        console.print("\n[green]All checks passed. Ready to build.[/green]")
    else:
        console.print("\n[yellow]Some checks failed. Fix the issues above before building.[/yellow]")
        raise typer.Exit(1)
