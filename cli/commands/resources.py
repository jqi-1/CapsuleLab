import typer
from rich.console import Console
from rich.table import Table

from capsulelab.services import project_service, resource_service

console = Console()
resources_cmd = typer.Typer(name="resources", help="Show lightweight local resource status", no_args_is_help=True)


@resources_cmd.command("status")
def resources_status(path: str | None = typer.Option(None, "--path", "-p", help="Project directory")):
    project_path = project_service.resolve_project_path(path)
    status = resource_service.project_resources(project_path)

    table = Table(title="Resources")
    table.add_column("Resource", style="cyan")
    table.add_column("Status")
    table.add_column("Detail")
    disk = status["disk"]
    table.add_row("Disk", f"{disk['free_percent']}% free", f"{disk['free_bytes']} bytes free at {disk['path']}")
    gpu = status["gpu"]
    if gpu["available"]:
        for item in gpu["gpus"]:
            table.add_row("GPU", item["name"], f"{item['utilization_percent']}% util, {item['memory_used_mb']}/{item['memory_total_mb']} MB")
    else:
        table.add_row("GPU", "Unavailable", "nvidia-smi not detected")
    console.print(table)
