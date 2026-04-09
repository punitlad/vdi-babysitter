"""vdi-babysitter — VDI session management CLI."""

import sys
import typer

from vdi_babysitter.config import get_active_profile, set_active_profile
from vdi_babysitter.providers.citrix import commands as citrix_commands

app = typer.Typer(
    name="vdi-babysitter",
    help="VDI session management CLI.",
    no_args_is_help=True,
    add_completion=False,
)

citrix_app = typer.Typer(
    help="Citrix provider commands.",
    no_args_is_help=True,
)
app.add_typer(citrix_app, name="citrix")

citrix_app.command("connect")(citrix_commands.connect)
citrix_app.command("disconnect")(citrix_commands.disconnect)
citrix_app.command("status")(citrix_commands.status)


@app.command()
def use(
    profile: str = typer.Argument(..., help="Profile name to activate."),
) -> None:
    """Set the active profile (persisted across invocations)."""
    set_active_profile(profile)
    print(f"Active profile set to '{profile}'.", file=sys.stderr)
