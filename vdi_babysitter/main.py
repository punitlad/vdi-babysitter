"""vdi-babysitter — VDI session management CLI."""

import sys
import typer
from importlib.metadata import version as _pkg_version

from vdi_babysitter._version import __sha__
from vdi_babysitter.config import get_active_profile, set_active_profile
from vdi_babysitter.configure_commands import configure_app
from vdi_babysitter.providers.citrix import commands as citrix_commands

app = typer.Typer(
    name="vdi-babysitter",
    help="VDI session management CLI.",
    invoke_without_command=True,
    add_completion=False,
)


@app.callback()
def _root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        print("Error: command argument required.", file=sys.stderr)
        print(ctx.get_help())
        raise typer.Exit(1)

citrix_app = typer.Typer(
    help="Citrix provider commands.",
    no_args_is_help=True,
)
app.add_typer(citrix_app, name="citrix")

app.add_typer(configure_app, name="configure")

citrix_app.command("connect")(citrix_commands.connect)
citrix_app.command("disconnect")(citrix_commands.disconnect)
citrix_app.command("status")(citrix_commands.status)


@app.command()
def version() -> None:
    """Show the installed version."""
    if __sha__:
        print(__sha__)
    else:
        print(f"v{_pkg_version('vdi-babysitter')}")


@app.command()
def use(
    profile: str = typer.Argument(..., help="Profile name to activate."),
) -> None:
    """Set the active profile (persisted across invocations)."""
    set_active_profile(profile)
    print(f"Active profile set to '{profile}'.", file=sys.stderr)
