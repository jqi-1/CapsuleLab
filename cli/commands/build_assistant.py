import typer
from rich.console import Console
from rich.table import Table

from backend.services import build_assistant_service, project_service

console = Console()


def build_assistant(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    apply: bool = typer.Option(False, "--apply", help="Apply the first proposed build-script edit"),
):
    try:
        project_path = project_service.resolve_project_path(path)
        config = project_service.load_config(project_path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    project_id = project_service.get_project_id(config.name)

    if apply:
        try:
            result = build_assistant_service.apply_first_proposed_edit(project_id)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        if result["applied"]:
            console.print(f"[green]✓[/green] Applied suggestion to {result['path']}")
        else:
            console.print(f"[yellow]{result['reason']}[/yellow]")
        return

    try:
        report = build_assistant_service.analyze_failed_build(project_id)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Build Assistant[/bold] — {config.name}")
    console.print("[dim]Reads build logs and known build context files. Proposed edits require review and never trigger rebuilds.[/dim]")

    findings = Table(title="Findings")
    findings.add_column("Severity", style="bold")
    findings.add_column("Finding", style="cyan")
    findings.add_column("Suggestion")
    for finding in report.findings:
        findings.add_row(finding.severity, finding.label, finding.suggestion or finding.detail)
    console.print(findings)

    edits = Table(title="Proposed Build-Script Edits")
    edits.add_column("Path", style="cyan")
    edits.add_column("Action")
    edits.add_column("Content")
    edits.add_column("Rationale")
    for edit in report.proposed_edits:
        edits.add_row(edit.path, edit.action, edit.content, edit.rationale)
    console.print(edits)

    if report.proposed_edits:
        console.print("\n[yellow]Review the proposed edit, then run `cap build-assistant --apply` to append the first suggestion.[/yellow]")
