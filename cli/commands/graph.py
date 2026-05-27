import typer
from rich.console import Console
from rich.table import Table
from capsulelab.services import graph_service, project_service
from capsulelab.db.repositories import projects

console = Console()


def graph(
    index: bool = typer.Option(False, "--index", "-i", help="Index project files"),
    summary: bool = typer.Option(False, "--summary", "-s", help="Show project summary"),
    project_id: str = typer.Option(None, "--project", "-p", help="Project ID"),
):
    if not project_id:
        try:
            path = project_service.resolve_project_path()
        except FileNotFoundError:
            console.print("[red]No project found. Use --project or run from a project directory.[/red]")
            raise typer.Exit(1)
        config = project_service.load_config(str(path))
        project_id = project_service.get_project_id(config.name)

    row = projects.get(project_id)
    if not row:
        console.print(f"[red]Project '{project_id}' not found in database. Register it with 'cap project register'.[/red]")
        raise typer.Exit(1)

    if index:
        g = graph_service.index_project(project_id, row["path"])
        console.print(f"[green]Indexed {len(g.nodes)} nodes, {len(g.edges)} edges[/green]")
        table = Table(title="Graph Nodes")
        table.add_column("ID", style="cyan")
        table.add_column("Kind", style="magenta")
        table.add_column("Label", style="green")
        for n in g.nodes:
            table.add_row(n.id, n.kind, n.label)
        console.print(table)

    if summary or not index:
        s = graph_service.summary(project_id, row["path"])
        table = Table(title=f"Project Summary: {s['project_name']}")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Node count", str(s["node_count"]))
        table.add_row("Edge count", str(s["edge_count"]))
        table.add_row("Has Dockerfile", "✓" if s["has_dockerfile"] else "—")
        table.add_row("Has tests", "✓" if s["has_tests"] else "—")
        table.add_row("Has README", "✓" if s["has_readme"] else "—")
        table.add_row("Has data", "✓" if s["has_data"] else "—")
        table.add_row("Source files", str(len(s["source_files"])))
        table.add_row("Notebooks", str(len(s["notebooks"])))
        console.print(table)
