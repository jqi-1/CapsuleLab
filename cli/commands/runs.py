import typer
from rich.console import Console
from rich.table import Table

from capsulelab.db.sqlite import init_db
from capsulelab.services import project_service, run_service

console = Console()
runs_cmd = typer.Typer(name="runs", help="Track lightweight local experiment runs", no_args_is_help=True)


def _project(path: str | None):
    project_path = project_service.resolve_project_path(path)
    config = project_service.load_config(project_path)
    return project_path, config, project_service.get_project_id(config.name)


@runs_cmd.command("start")
def run_start(
    name: str = typer.Argument(..., help="Run name"),
    notes: str | None = typer.Option(None, "--notes", "-n", help="Optional run notes"),
    path: str | None = typer.Option(None, "--path", "-p", help="Project directory"),
):
    init_db()
    project_path, _, project_id = _project(path)
    run = run_service.start_run(project_id, name, project_path, notes=notes)
    console.print(f"[green]✓[/green] Run started: {run['id']}")
    console.print(f"  [dim]Artifacts:[/dim] {run['artifact_path']}")


@runs_cmd.command("finish")
def run_finish(
    run_id: str = typer.Argument(..., help="Run ID"),
    status: str = typer.Option("finished", "--status", "-s", help="Final status"),
):
    run_service.finish_run(run_id, status)
    console.print(f"[green]✓[/green] Run {run_id} marked {status}")


@runs_cmd.command("list")
def run_list(path: str | None = typer.Option(None, "--path", "-p", help="Project directory")):
    _, _, project_id = _project(path)
    rows = run_service.list_project_runs(project_id)
    table = Table(title="Experiment Runs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Started")
    table.add_column("Artifacts")
    for row in rows:
        table.add_row(row["id"], row["name"], row["status"], row["started_at"], row["artifact_path"] or "-")
    console.print(table)
