import typer

from cli.commands import build, build_assistant, doctor, init, logs, start, stop
from cli.commands.app import app_cmd
from cli.commands.compose import compose_cmd
from cli.commands.data import data_cmd
from cli.commands.graph import graph as graph_cmd
from cli.commands.ide import ide_cmd
from cli.commands.images import images_cmd
from cli.commands.location import location_cmd
from cli.commands.metadata import metadata_cmd
from cli.commands.package import package_cmd
from cli.commands.profile import profile as profile_cmd
from cli.commands.project import project_cmd
from cli.commands.registry import registry_cmd
from cli.commands.resources import resources_cmd
from cli.commands.runs import runs_cmd
from cli.commands.secrets import secrets_cmd
from cli.commands.settings import settings_cmd
from cli.commands.shell import attach as attach_cmd
from cli.commands.shell import exec_cmd
from cli.commands.shell import shell as shell_cmd
from cli.commands.sync import sync_cmd
from cli.commands.template import template_cmd

cli = typer.Typer(
    name="cap",
    help="CapsuleLab - local-first containerized project runtime manager",
    no_args_is_help=True,
)

cli.command()(init.init)
cli.command()(doctor.doctor)
cli.command()(build.build)
cli.command(name="build-assistant")(build_assistant.build_assistant)
cli.command()(start.start)
cli.command()(stop.stop)
cli.command()(logs.logs)
cli.command(name="shell")(shell_cmd)
cli.command(name="exec")(exec_cmd)
cli.command(name="attach")(attach_cmd)
cli.add_typer(app_cmd, name="app")
cli.add_typer(location_cmd, name="location")
cli.add_typer(compose_cmd, name="compose")
cli.add_typer(sync_cmd, name="sync")
cli.add_typer(template_cmd, name="template")
cli.add_typer(project_cmd, name="project")
cli.add_typer(secrets_cmd, name="secrets")
cli.add_typer(runs_cmd, name="runs")
cli.add_typer(resources_cmd, name="resources")
cli.add_typer(images_cmd, name="images")
cli.add_typer(data_cmd, name="data")
cli.add_typer(ide_cmd, name="ide")
cli.add_typer(package_cmd, name="package")
cli.command(name="profile")(profile_cmd)
cli.command(name="graph")(graph_cmd)
cli.add_typer(registry_cmd, name="registry")
cli.add_typer(metadata_cmd, name="metadata")
cli.add_typer(settings_cmd, name="settings")

if __name__ == "__main__":
    cli()
