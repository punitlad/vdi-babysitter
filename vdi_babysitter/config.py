"""Config file loading, profile resolution, and validation."""

import os
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

CONFIG_DIR = Path.home() / ".vdi-babysitter"
GLOBAL_CONFIG = CONFIG_DIR / "config.yaml"
LOCAL_CONFIG = Path.cwd() / ".vdi-babysitter.yaml"
CURRENT_PROFILE_FILE = CONFIG_DIR / "current_profile"

# OTP is intentionally excluded — it must always be passed explicitly.
VALID_PROFILE_KEYS = {
    "storefront_url",
    "username",
    "password",
    "desktop_name",
    "pingid_url",
    "pingid_otp_text",
    "output_dir",
    "max_retries",
    "restart_wait",
    "restart_first",
    "download_only",
    "no_headless",
    "timeout",
    "otp_cmd",
}


def get_active_profile(profile_flag: Optional[str] = None) -> str:
    """Resolve active profile: flag → env var → saved current → 'default'."""
    if profile_flag:
        return profile_flag
    env = os.environ.get("VDI_BABYSITTER_PROFILE")
    if env:
        return env
    if CURRENT_PROFILE_FILE.exists():
        name = CURRENT_PROFILE_FILE.read_text().strip()
        if name:
            return name
    return "default"


def set_active_profile(profile: str) -> None:
    """Persist the active profile name."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_PROFILE_FILE.write_text(profile)


def load_profile(profile: str) -> dict[str, Any]:
    """
    Load config values for the given profile.

    Searches project-local config first, falls back to global.
    Exits with a clear error if unknown keys are found.
    """
    config_file = LOCAL_CONFIG if LOCAL_CONFIG.exists() else GLOBAL_CONFIG
    if not config_file.exists():
        return {}

    raw = yaml.safe_load(config_file.read_text()) or {}
    profiles: dict = raw.get("profiles", {})

    for prof_name, prof_data in profiles.items():
        if not isinstance(prof_data, dict):
            continue
        unknown = set(prof_data.keys()) - VALID_PROFILE_KEYS
        if unknown:
            print(
                f"Error: Unknown config key(s) in profile '{prof_name}': "
                f"{', '.join(sorted(unknown))}\n"
                f"  Config file: {config_file}\n"
                f"  Valid keys: {', '.join(sorted(VALID_PROFILE_KEYS))}",
                file=sys.stderr,
            )
            raise SystemExit(1)

    return profiles.get(profile, {})


def resolve(flag_value: Optional[Any], config_value: Optional[Any], default: Any = None) -> Any:
    """Return the first non-None value: flag → config → default."""
    if flag_value is not None:
        return flag_value
    if config_value is not None:
        return config_value
    return default
