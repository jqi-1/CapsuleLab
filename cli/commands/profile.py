import typer
from rich.console import Console
from rich.table import Table
from capsulelab.services import profile_service

console = Console()


def profile(
    mode: str = typer.Argument(None, help="Profile mode: research, deployable, opensource"),
):
    if mode:
        from capsulelab.models.project import ProjectMode
        try:
            pm = ProjectMode(mode)
        except ValueError:
            console.print(f"[red]Invalid mode '{mode}'. Use: research, deployable, opensource[/red]")
            raise typer.Exit(1)
        p = profile_service.get_profile(pm)
        table = Table(title=f"Profile: {p['label']}")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Mode", p["mode"])
        table.add_row("Label", p["label"])
        table.add_row("Description", p["description"])
        table.add_row("Presets", ", ".join(f"{k}={v}" for k, v in p["presets"].items()))
        table.add_row("Recommended apps", ", ".join(p["recommended_apps"]) or "None")
        table.add_row("Required directories", ", ".join(p["required_dirs"]) or "None")
        console.print(table)
    else:
        profiles = profile_service.list_profiles()
        table = Table(title="Available Profiles")
        table.add_column("Mode", style="cyan")
        table.add_column("Label", style="green")
        table.add_column("Description")
        for p in profiles:
            table.add_row(p["mode"], p["label"], p["description"])
        console.print(table)
