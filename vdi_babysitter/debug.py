"""Debug mode activation and config loading."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from vdi_babysitter.config import CONFIG_DIR

DEBUG_CONFIG_PATH = CONFIG_DIR / "debug.yaml"

VALID_DEBUG_KEYS = {
    "playwright_trace",
    "playwright_slow_mo",
    "capture_screenshots",
    "capture_html",
    "keep_runs",
}


@dataclass
class DebugConfig:
    playwright_trace: bool = True
    playwright_slow_mo: int = 0
    capture_screenshots: bool = False
    capture_html: bool = False
    keep_runs: int = 5


def load_debug_config(debug_config_path: Optional[Path] = None) -> Optional[DebugConfig]:
    """Return a DebugConfig if VDI_BABYSITTER_DEBUG is set, else None.

    Hard fails if the env var is set but debug.yaml is missing or has unknown keys.
    """
    if not os.environ.get("VDI_BABYSITTER_DEBUG"):
        return None

    path = debug_config_path or DEBUG_CONFIG_PATH

    if not path.exists():
        print(
            f"Error: VDI_BABYSITTER_DEBUG is set but {path} was not found.\n"
            f"  Create {path} to enable debug mode.\n"
            f"  See the 'Debug mode' section in README for the required format.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    raw = yaml.safe_load(path.read_text()) or {}

    unknown = set(raw.keys()) - VALID_DEBUG_KEYS
    if unknown:
        print(
            f"Error: Unknown key(s) in {path}: {', '.join(sorted(unknown))}\n"
            f"  Valid keys: {', '.join(sorted(VALID_DEBUG_KEYS))}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return DebugConfig(
        playwright_trace=raw.get("playwright_trace", True),
        playwright_slow_mo=raw.get("playwright_slow_mo", 0),
        capture_screenshots=raw.get("capture_screenshots", False),
        capture_html=raw.get("capture_html", False),
        keep_runs=raw.get("keep_runs", 5),
    )
