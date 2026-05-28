import json as json_mod

import typer
from rich.console import Console
from rich.table import Table

from capsulelab.services import doctor_service, project_service

console = Console()


def doctor(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    project_id: str = typer.Option(None, "--project", help="Registered project ID"),
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON report"),
):
    if project_id:
        _project_doctor(project_id, json_output)
        return

    try:
        project_path = project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)

    report = doctor_service.project_doctor_for_path(project_path)
    _print_report(report, json_output)


def _project_doctor(project_id: str, json_output: bool = False):
    try:
        report = doctor_service.project_doctor(project_id)
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)

    _print_report(report, json_output)


def _print_report(report: doctor_service.DoctorReport, json_output: bool = False):
    if json_output:
        print(json_mod.dumps(report.to_dict(), indent=2))
        return

    table = Table(title=f"Doctor Report — {report.project_name} (project: {report.project_path})")
    table.add_column("Check", style="cyan")
    table.add_column("Severity", style="bold")
    table.add_column("Status", style="bold")
    table.add_column("Detail")

    for check in report.checks:
        status = "[green]✓[/green]" if check.ok else "[red]✗[/red]"
        sev_str = {
            "info": "[blue]info[/blue]",
            "warning": "[yellow]warn[/yellow]",
            "error": "[red]error[/red]",
            "critical": "[red bold]CRIT[/red bold]",
        }.get(check.severity.value, check.severity.value)
        table.add_row(check.label, sev_str, status, check.detail)

    console.print(table)

    errors = report.errors()
    warnings = report.warnings()
    if errors:
        console.print(f"\n[red]{len(errors)} error(s) found. Fix them before building.[/red]")
        raise typer.Exit(1)
    if warnings:
        console.print(f"\n[yellow]{len(warnings)} warning(s) found. Review before building.[/yellow]")
    if report.all_ok():
        console.print("\n[green]All checks passed. Ready to build.[/green]")
