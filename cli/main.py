import typer
from cli.commands import init, doctor, build, start, stop, logs
from cli.commands.app import app_cmd

cli = typer.Typer(
    name="cap",
    help="CapsuleLab - local-first containerized project runtime manager",
    no_args_is_help=True,
)

cli.command()(init.init)
cli.command()(doctor.doctor)
cli.command()(build.build)
cli.command()(start.start)
cli.command()(stop.stop)
cli.command()(logs.logs)
cli.add_typer(app_cmd, name="app")

if __name__ == "__main__":
    cli()
