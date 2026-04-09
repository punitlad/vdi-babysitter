"""Typer commands for the citrix provider group."""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer

from vdi_babysitter.config import get_active_profile, load_profile, resolve
from vdi_babysitter.providers.citrix.provider import CitrixConfig, CitrixProvider

log = logging.getLogger(__name__)


def _setup_logging(verbose: bool, debug: bool) -> None:
    level = logging.DEBUG if debug else (logging.INFO if verbose else logging.ERROR)
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def connect(
    storefront_url: Optional[str] = typer.Option(None, "--storefront-url", envvar="CITRIX_STOREFRONT", help="Full StoreFront URL."),
    username: Optional[str] = typer.Option(None, "--username", envvar="CITRIX_USER", help="SSO username."),
    password: Optional[str] = typer.Option(None, "--password", envvar="CITRIX_PASS", help="SSO password."),
    desktop_name: Optional[str] = typer.Option(None, "--desktop-name", envvar="CITRIX_APP", help="Desktop display name in StoreFront."),
    pingid_url: Optional[str] = typer.Option(None, "--pingid-url", envvar="CITRIX_PINGID_URL", help="URL pattern to match PingID redirect."),
    pingid_otp_text: Optional[str] = typer.Option(None, "--pingid-otp-text", envvar="CITRIX_YUBIKEY_TEXT", help="Button text for OTP method on PingID page."),
    otp: Optional[str] = typer.Option(None, "--otp", help="OTP value. Mutually exclusive with --otp-cmd. Never read from config or env."),
    otp_cmd: Optional[str] = typer.Option(None, "--otp-cmd", help="Shell command whose stdout is the OTP. Mutually exclusive with --otp."),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Directory to save session.ica."),
    max_retries: Optional[int] = typer.Option(None, "--max-retries", envvar="MAX_RETRIES", help="Max restart attempts (0 = infinite)."),
    restart_wait: Optional[int] = typer.Option(None, "--restart-wait", envvar="RESTART_WAIT", help="Seconds to wait after VM restart."),
    restart_first: Optional[bool] = typer.Option(None, "--restart-first", envvar="CITRIX_RESTART_FIRST", help="Restart desktop before first attempt."),
    no_headless: bool = typer.Option(False, "--no-headless", help="Show the browser window."),
    download_only: bool = typer.Option(False, "--download-only", envvar="CITRIX_DOWNLOAD_ONLY", help="Exit after saving ICA, skip Workspace launch."),
    timeout: Optional[int] = typer.Option(None, "--timeout", help="Max wall-clock seconds for the entire connect operation."),
    profile: Optional[str] = typer.Option(None, "--profile", envvar="VDI_BABYSITTER_PROFILE", help="Config profile to use."),
    output: str = typer.Option("text", "--output", help="Output format: text, json."),
    verbose: bool = typer.Option(False, "--verbose", help="Show INFO-level progress logs."),
    debug: bool = typer.Option(False, "--debug", help="Show DEBUG-level logs."),
) -> None:
    """Connect to a Citrix VDI session."""
    _setup_logging(verbose, debug)

    if otp and otp_cmd:
        print("Error: --otp and --otp-cmd are mutually exclusive.", file=sys.stderr)
        raise typer.Exit(1)

    active_profile = get_active_profile(profile)
    cfg = load_profile(active_profile)

    config = CitrixConfig(
        storefront_url=resolve(storefront_url, cfg.get("storefront_url")),
        username=resolve(username, cfg.get("username")),
        password=resolve(password, cfg.get("password")),
        desktop_name=resolve(desktop_name, cfg.get("desktop_name"), "My Windows 11 Desktop"),
        pingid_url=resolve(pingid_url, cfg.get("pingid_url"), "**/pingid/**"),
        pingid_otp_text=resolve(pingid_otp_text, cfg.get("pingid_otp_text"), "YubiKey"),
        otp=otp,
        otp_cmd=resolve(otp_cmd, cfg.get("otp_cmd")),
        output_dir=resolve(
            output_dir,
            Path(cfg["output_dir"]) if cfg.get("output_dir") else None,
            Path.home() / ".vdi-babysitter" / "output",
        ),
        max_retries=resolve(max_retries, cfg.get("max_retries"), 0),
        restart_wait=resolve(restart_wait, cfg.get("restart_wait"), 120),
        restart_first=resolve(restart_first, cfg.get("restart_first"), False),
        headless=not no_headless,
        download_only=download_only or bool(cfg.get("download_only", False)),
        timeout=resolve(timeout, cfg.get("timeout")),
    )

    missing = [
        flag
        for flag, val in [
            ("--storefront-url", config.storefront_url),
            ("--username", config.username),
            ("--password", config.password),
        ]
        if not val
    ]
    if missing:
        print(f"Error: Missing required options: {', '.join(missing)}", file=sys.stderr)
        raise typer.Exit(1)

    provider = CitrixProvider(config)
    try:
        provider.connect()
    except Exception as e:
        if debug:
            raise
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(1)

    if output == "json":
        print(json.dumps({"status": "connected"}))


def disconnect(
    profile: Optional[str] = typer.Option(None, "--profile", envvar="VDI_BABYSITTER_PROFILE", help="Config profile to use."),
    output: str = typer.Option("text", "--output", help="Output format: text, json."),
    verbose: bool = typer.Option(False, "--verbose"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Disconnect the active Citrix session."""
    _setup_logging(verbose, debug)

    result = subprocess.run(["pkill", "-x", "Citrix Workspace"], capture_output=True)
    if result.returncode != 0:
        print("Error: No active Citrix Workspace session found.", file=sys.stderr)
        raise typer.Exit(1)

    log.info("Citrix Workspace terminated.")
    if output == "json":
        print(json.dumps({"status": "disconnected"}))


def status(
    watch: bool = typer.Option(False, "--watch", help="Continuously poll connection status."),
    interval: int = typer.Option(30, "--interval", help="Poll interval in seconds (--watch only)."),
    profile: Optional[str] = typer.Option(None, "--profile", envvar="VDI_BABYSITTER_PROFILE", help="Config profile to use."),
    output: str = typer.Option("text", "--output", help="Output format: text, json."),
    verbose: bool = typer.Option(False, "--verbose"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Check whether a Citrix session is connected (TCP)."""
    _setup_logging(verbose, debug)

    def _connected() -> bool:
        result = subprocess.run(
            ["lsof", "-i", "-nP"], capture_output=True, text=True, check=False
        )
        return "Citrix" in result.stdout and "ESTABLISHED" in result.stdout

    if not watch:
        connected = _connected()
        if output == "json":
            print(json.dumps({"connected": connected}))
        else:
            print("connected" if connected else "not connected", file=sys.stderr)
        raise typer.Exit(0 if connected else 1)

    log.info("Watching connection (interval: %ds). Ctrl-C to stop.", interval)
    try:
        while True:
            if not _connected():
                print("Error: Connection lost.", file=sys.stderr)
                raise typer.Exit(1)
            log.info("Connected.")
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
