import typer
from rich.console import Console
from rich.table import Table
from backend.services import registry_service

console = Console()
registry_cmd = typer.Typer(name="registry", help="Container registry operations")


@registry_cmd.command("list")
def list_registries():
    registries = registry_service.list_registries()
    table = Table(title="Container Registries")
    table.add_column("Key", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("URL", style="blue")
    table.add_column("Logged In", style="yellow")
    for key, r in registries.items():
        logged = "✓" if r["logged_in"] else "—"
        table.add_row(key, r["name"], r["url"], logged)
    console.print(table)


@registry_cmd.command("login")
def login(
    registry: str = typer.Argument(..., help="Registry key (dockerhub, ghcr, gitlab, ngc, huggingface)"),
    username: str = typer.Option(..., "--username", "-u", prompt=True, help="Username"),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, help="Password or token"),
):
    try:
        result = registry_service.login(registry, username, password)
        if result["ok"]:
            console.print(f"[green]✓ Logged into {registry} as {username}[/green]")
        else:
            console.print(f"[red]Login failed: {result['error']}[/red]")
            raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@registry_cmd.command("logout")
def logout(registry: str = typer.Argument(..., help="Registry key")):
    try:
        result = registry_service.logout(registry)
        if result["ok"]:
            console.print(f"[green]✓ Logged out of {registry}[/green]")
        else:
            console.print(f"[red]Logout failed: {result['error']}[/red]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@registry_cmd.command("push")
def push(
    image: str = typer.Argument(..., help="Image tag to push"),
    registry: str = typer.Option(None, "--registry", "-r", help="Registry key hint"),
):
    result = registry_service.push_image(image, registry)
    if result["ok"]:
        console.print(f"[green]✓ Pushed {image}[/green]")
    else:
        console.print(f"[red]Push failed: {result['error']}[/red]")
        raise typer.Exit(1)


@registry_cmd.command("pull")
def pull(image: str = typer.Argument(..., help="Image tag to pull")):
    result = registry_service.pull_image(image)
    if result["ok"]:
        console.print(f"[green]✓ Pulled {image}[/green]")
    else:
        console.print(f"[red]Pull failed: {result['error']}[/red]")
        raise typer.Exit(1)


@registry_cmd.command("tag")
def tag(source: str = typer.Argument(..., help="Source image tag"), target: str = typer.Argument(..., help="Target image tag")):
    result = registry_service.tag_image(source, target)
    if result["ok"]:
        console.print(f"[green]✓ Tagged {source} -> {target}[/green]")
    else:
        console.print(f"[red]Tag failed: {result['error']}[/red]")
        raise typer.Exit(1)


@registry_cmd.command("status")
def status():
    creds = registry_service.credential_status()
    if creds:
        table = Table(title="Saved Registry Credentials")
        table.add_column("Registry", style="cyan")
        table.add_column("Username", style="green")
        for key, info in creds.items():
            table.add_row(key, info.get("username", "?"))
        console.print(table)
    else:
        console.print("[yellow]No saved registry credentials[/yellow]")
