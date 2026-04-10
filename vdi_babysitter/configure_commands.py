"""configure command group: interactive wizard + imperative set/show/list."""

import sys
from typing import Optional

import typer

from vdi_babysitter.config import (
    GLOBAL_CONFIG,
    VALID_PROFILE_KEYS,
    get_active_profile,
    list_profiles,
    load_profile,
    write_profile,
)

# Ordered fields for the wizard, grouped logically.
# Each entry: (key, prompt label, is_secret, is_int, is_bool, default_hint)
_WIZARD_FIELDS = [
    # Connection
    ("storefront_url",  "StoreFront URL",                  False, False, False, None),
    ("username",        "SSO username",                    False, False, False, None),
    ("password",        "SSO password",                    True,  False, False, None),
    ("desktop_name",    "Desktop name",                    False, False, False, "My Windows 11 Desktop"),
    # PingID / OTP
    ("pingid_url",      "PingID redirect URL pattern",     False, False, False, "**/pingid/**"),
    ("pingid_otp_text", "PingID OTP button text",          False, False, False, "YubiKey"),
    ("otp_cmd",         "OTP shell command (--otp-cmd)",   False, False, False, None),
    # Behaviour
    ("output_dir",      "ICA output directory",            False, False, False, "~/.vdi-babysitter/output"),
    ("max_retries",     "Max retries (0 = infinite)",      False, True,  False, "0"),
    ("restart_wait",    "Restart wait (seconds)",          False, True,  False, "120"),
    ("timeout",         "Connect timeout (seconds)",       False, True,  False, None),
    ("restart_first",   "Restart before first attempt",    False, False, True,  "n"),
    ("download_only",   "Download only (skip Workspace)",  False, False, True,  "n"),
    ("no_headless",     "Show browser window",             False, False, True,  "n"),
]


configure_app = typer.Typer(
    help="Manage configuration profiles.",
    no_args_is_help=False,
    invoke_without_command=True,
)


@configure_app.callback()
def configure_default(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None, "--profile", envvar="VDI_BABYSITTER_PROFILE",
        help="Profile to configure (default: active profile).",
    ),
) -> None:
    """Interactive wizard to create or edit a config profile."""
    if ctx.invoked_subcommand is not None:
        return

    active = get_active_profile(profile)
    current = load_profile(active)

    print(f"Configuring profile '{active}'. Press Enter to keep the current value.\n",
          file=sys.stderr)

    updated: dict = dict(current)

    for key, label, is_secret, is_int, is_bool, hint in _WIZARD_FIELDS:
        cur = current.get(key)

        if is_bool:
            cur_display = ("y" if cur else "n") if cur is not None else hint
            raw = typer.prompt(f"  {label} [y/n]", default=cur_display or "n")
            updated[key] = raw.strip().lower() in ("y", "yes", "true", "1")

        elif is_int:
            cur_display = str(cur) if cur is not None else hint
            raw = typer.prompt(f"  {label}", default=cur_display or "")
            if raw.strip():
                try:
                    updated[key] = int(raw.strip())
                except ValueError:
                    print(f"  Warning: '{raw}' is not an integer — skipping {key}.",
                          file=sys.stderr)
            elif key in updated:
                del updated[key]

        elif is_secret:
            cur_display = "********" if cur else ""
            raw = typer.prompt(
                f"  {label}" + (f" [current: {cur_display}]" if cur else ""),
                default="",
                hide_input=True,
            )
            if raw.strip():
                updated[key] = raw.strip()
            # Empty = keep existing (already in updated dict)

        else:
            cur_display = cur or hint or ""
            raw = typer.prompt(f"  {label}", default=cur_display)
            if raw.strip():
                updated[key] = raw.strip()
            elif key in updated:
                del updated[key]

    # Strip None / empty values before saving
    cleaned = {k: v for k, v in updated.items() if v is not None and v != ""}
    config_file = write_profile(active, cleaned)
    print(f"\nProfile '{active}' saved to {config_file}.", file=sys.stderr)


@configure_app.command("set")
def configure_set(
    key: str = typer.Argument(..., help="Config key to set."),
    value: str = typer.Argument(..., help="Value to assign."),
    profile: Optional[str] = typer.Option(
        None, "--profile", envvar="VDI_BABYSITTER_PROFILE",
        help="Profile to update (default: active profile).",
    ),
) -> None:
    """Set a single config key in a profile."""
    if key not in VALID_PROFILE_KEYS:
        print(
            f"Error: '{key}' is not a valid config key.\n"
            f"Valid keys: {', '.join(sorted(VALID_PROFILE_KEYS))}",
            file=sys.stderr,
        )
        raise typer.Exit(1)

    active = get_active_profile(profile)
    data = dict(load_profile(active))
    data[key] = value
    config_file = write_profile(active, data)
    print(f"Set {key}={value!r} in profile '{active}' ({config_file}).", file=sys.stderr)


@configure_app.command("show")
def configure_show(
    profile: Optional[str] = typer.Option(
        None, "--profile", envvar="VDI_BABYSITTER_PROFILE",
        help="Profile to display (default: active profile).",
    ),
) -> None:
    """Show all config values for a profile."""
    active = get_active_profile(profile)
    data = load_profile(active)

    if not data:
        print(f"Profile '{active}' is empty or does not exist.", file=sys.stderr)
        raise typer.Exit(1)

    print(f"Profile: {active}\n", file=sys.stderr)
    for key, val in sorted(data.items()):
        display = "********" if key == "password" and val else val
        print(f"  {key}: {display}", file=sys.stderr)


@configure_app.command("list-profiles")
def configure_list_profiles() -> None:
    """List all configured profiles."""
    profiles = list_profiles()
    if not profiles:
        print("No profiles configured. Run `vdi-babysitter configure` to create one.",
              file=sys.stderr)
        raise typer.Exit(1)
    for name in profiles:
        print(name)
