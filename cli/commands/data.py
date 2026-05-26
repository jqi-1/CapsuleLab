from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from backend.services import project_service

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
