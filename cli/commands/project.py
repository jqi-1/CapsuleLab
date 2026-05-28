import typer
from rich.console import Console
from rich.table import Table

from capsulelab.services import git_service, project_import_service, project_service

console = Console()
project_cmd = typer.Typer(name="project", help="Import and repair project inventory", no_args_is_help=True)
git_cmd = typer.Typer(name="git", help="Project Git operations", no_args_is_help=True)
project_cmd.add_typer(git_cmd, name="git")


@project_cmd.command("list")
def project_list():
    rows = project_import_service.inventory()
    table = Table(title="Project Inventory")
    table.add_column("Project", style="cyan")
    table.add_column("ID")
    table.add_column("Path")
    for row in rows:
        table.add_row(row["name"], row["id"], row["path"])
    console.print(table)


@project_cmd.command("import")
def project_import(
    source: str = typer.Argument(..., help="Existing project directory or Git URL"),
    dest: str | None = typer.Option(None, "--dest", "-d", help="Clone destination when source is a Git URL"),
    name: str | None = typer.Option(None, "--name", "-n", help="Project name"),
    scaffold: bool = typer.Option(True, "--scaffold/--no-scaffold", help="Create .workbench/project.yaml when missing"),
):
    try:
        result = project_import_service.import_project(source, dest=dest, name=name, scaffold=scaffold)

    except (git_service.GitError, project_import_service.GitError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Project imported: {result['name']} ({result['project_id']})")


def _project_path(path: str | None) -> str:
    try:
        return project_service.resolve_project_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@git_cmd.command("branches")
def project_git_branches(path: str = typer.Option(None, "--path", "-p", help="Project directory")):
    try:
        result = git_service.branches(_project_path(path))
    except git_service.GitError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    table = Table(title="Git Branches")
    table.add_column("Current")
    table.add_column("Branch", style="cyan")
    for branch in result["branches"]:
        table.add_row("*" if branch["current"] else "", branch["name"])
    console.print(table)


@git_cmd.command("switch")
def project_git_switch(
    branch: str = typer.Argument(..., help="Branch name"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    create: bool = typer.Option(False, "--create", "-c", help="Create the branch"),
):
    try:
        result = git_service.switch_branch(_project_path(path), branch, create=create)
    except git_service.GitError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Switched to {result['branch']}")


@git_cmd.command("commit")
def project_git_commit(
    message: str = typer.Argument(..., help="Commit message"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    all_changes: bool = typer.Option(True, "--all/--staged-only", help="Stage all changes before committing"),
):
    try:
        result = git_service.commit(_project_path(path), message, all_changes=all_changes)
    except git_service.GitError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    if result["status"] == "clean":
        console.print("[yellow]No changes to commit.[/yellow]")
    else:
        console.print(f"[green]✓[/green] Commit {result['commit']}")


@git_cmd.command("fetch")
def project_git_fetch(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
):
    _run_git_action(lambda p: git_service.fetch(p, remote=remote), path)


@git_cmd.command("pull")
def project_git_pull(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Branch name"),
):
    _run_git_action(lambda p: git_service.pull(p, remote=remote, branch=branch), path)


@git_cmd.command("push")
def project_git_push(
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Branch name"),
    set_upstream: bool = typer.Option(False, "--set-upstream", "-u", help="Set upstream branch"),
):
    _run_git_action(lambda p: git_service.push(p, remote=remote, branch=branch, set_upstream=set_upstream), path)


@git_cmd.command("publish")
def project_git_publish(
    remote_url: str = typer.Argument(..., help="Remote Git URL"),
    path: str = typer.Option(None, "--path", "-p", help="Project directory"),
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Branch name"),
):
    _run_git_action(lambda p: git_service.publish(p, remote_url, remote=remote, branch=branch), path)


def _run_git_action(action, path: str | None):
    try:
        result = action(_project_path(path))
    except git_service.GitError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] {result['status']}")
    if result.get("output"):
        console.print(result["output"])
