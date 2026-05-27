import typer
from rich.console import Console
from rich.table import Table

from capsulelab.services import image_service, project_service

console = Console()
images_cmd = typer.Typer(name="images", help="Inspect base image options and Dockerfile inputs", no_args_is_help=True)


@images_cmd.command("catalog")
def image_catalog():
    table = Table(title="Base Image Catalog")
    table.add_column("ID", style="cyan")
    table.add_column("Image")
    table.add_column("GPU")
    table.add_column("Description")
    for key, item in image_service.catalog().items():
        table.add_row(key, item["image"], "yes" if item["gpu"] else "no", item["description"])
    console.print(table)


@images_cmd.command("check")
def image_check(path: str | None = typer.Option(None, "--path", "-p", help="Project directory")):
    project_path = project_service.resolve_project_path(path)
    config = project_service.load_config(project_path)
    checks = image_service.byoc_checks(project_path, config.runtime.dockerfile)
    table = Table(title="Container Input Checks")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail")
    failed = False
    for check in checks:
        failed = failed or not check["ok"]
        table.add_row(check["label"], "[green]✓[/green]" if check["ok"] else "[red]✗[/red]", check["detail"])
    console.print(table)
    if failed:
        raise typer.Exit(1)
