from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from backend.services import project_service, model_service

console = Console()
data_cmd = typer.Typer(name="data", help="Manage dataset and cache metadata in project.yaml", no_args_is_help=True)

CACHE_PRESETS = {
    "huggingface": ("~/.cache/huggingface", "/root/.cache/huggingface"),
    "torch": ("~/.cache/torch", "/root/.cache/torch"),
    "pip": ("~/.cache/pip", "/root/.cache/pip"),
    "uv": ("~/.cache/uv", "/root/.cache/uv"),
    "npm": ("~/.npm", "/root/.npm"),
}


def _config_path(path: str | None) -> Path:
    project_path = project_service.resolve_project_path(path)
    return Path(project_path) / project_service.WORKBENCH_DIR / project_service.CONFIG_FILE


def _load_yaml(config_path: Path) -> dict:
    return yaml.safe_load(config_path.read_text()) or {}


def _save_yaml(config_path: Path, data: dict):
    config_path.write_text(yaml.safe_dump(data, sort_keys=False))


@data_cmd.command("list")
def data_list(path: str | None = typer.Option(None, "--path", "-p", help="Project directory")):
    config = project_service.load_config(project_service.resolve_project_path(path))
    table = Table(title="Datasets And Caches")
    table.add_column("Kind", style="cyan")
    table.add_column("Name/Source")
    table.add_column("Target")
    table.add_column("Mode")
    for dataset in config.datasets:
        table.add_row("dataset", dataset.name, dataset.target, "read-only" if dataset.read_only else "read-write")
    for cache in config.caches:
        table.add_row("cache", cache.source, cache.target, "read-write")
    console.print(table)


@data_cmd.command("add-dataset")
def add_dataset(
    name: str = typer.Argument(..., help="Dataset name"),
    source: str = typer.Argument(..., help="Host path"),
    target: str = typer.Argument(..., help="Container mount target"),
    writable: bool = typer.Option(False, "--writable", help="Mount read-write"),
    path: str | None = typer.Option(None, "--path", "-p", help="Project directory"),
):
    config_path = _config_path(path)
    data = _load_yaml(config_path)
    datasets = data.setdefault("datasets", [])
    datasets.append({"name": name, "path": source, "target": target, "read_only": not writable})
    _save_yaml(config_path, data)
    console.print(f"[green]✓[/green] Dataset {name} added")


@data_cmd.command("add-cache")
def add_cache(
    preset: str = typer.Argument(..., help=f"Preset: {', '.join(CACHE_PRESETS)}"),
    path: str | None = typer.Option(None, "--path", "-p", help="Project directory"),
):
    if preset not in CACHE_PRESETS:
        console.print(f"[red]Unknown cache preset '{preset}'.[/red]")
        console.print(f"Available: {', '.join(CACHE_PRESETS)}")
        raise typer.Exit(1)
    source, target = CACHE_PRESETS[preset]
    config_path = _config_path(path)
    data = _load_yaml(config_path)
    caches = data.setdefault("caches", [])
    if not any(cache.get("source") == source for cache in caches):
        caches.append({"source": source, "target": target})
        _save_yaml(config_path, data)
    console.print(f"[green]✓[/green] Cache preset {preset} configured")


@data_cmd.command("model-register")
def model_register(
    name: str = typer.Argument(..., help="Model name"),
    version: str = typer.Argument(..., help="Model version"),
    artifact: str = typer.Argument(..., help="Path to model artifact"),
    source: str = typer.Option("local", "--source", "-s", help="Source label, registry, or URL"),
):
    try:
        record = model_service.register_model(name, version, artifact, source=source)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Registered model {record['name']}:{record['version']}")
    console.print(f"  ID: {record['id']}")
    console.print(f"  SHA-256: {record['sha256']}")


@data_cmd.command("model-list")
def model_list(name: str | None = typer.Option(None, "--name", "-n", help="Filter by model name")):
    records = model_service.list_models(name)
    table = Table(title="Local Model Registry")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Source")
    table.add_column("SHA-256")
    for record in records:
        table.add_row(record["id"], record["name"], record["version"], record["source"], record["sha256"][:12])
    console.print(table)


@data_cmd.command("model-verify")
def model_verify(model_id: str = typer.Argument(..., help="Model record ID")):
    try:
        result = model_service.verify_model(model_id)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    if result["ok"]:
        console.print(f"[green]✓[/green] {result['name']}:{result['version']} integrity verified")
    else:
        console.print(f"[red]Integrity check failed:[/red] {result['error']}")
        raise typer.Exit(1)
