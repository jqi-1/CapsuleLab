import typer
from rich.console import Console
from rich.table import Table

from backend.services import template_service

console = Console()
template_cmd = typer.Typer(name="template", help="Validate maintained project templates", no_args_is_help=True)


@template_cmd.command("validate")
def template_validate(
    name: str | None = typer.Argument(None, help="Template name. Omit to validate all maintained templates."),
):
    names = [name] if name else template_service.list_maintained_templates()
    failed = False

    for template_name in names:
        checks = template_service.validate_template(template_name)
        table = Table(title=f"Template Validation — {template_name}")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Detail")
        for check in checks:
            if not check.ok:
                failed = True
            table.add_row(check.label, "[green]✓[/green]" if check.ok else "[red]✗[/red]", check.detail)
        console.print(table)

    if failed:
        raise typer.Exit(1)
