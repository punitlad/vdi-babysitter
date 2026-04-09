#!/usr/bin/env python3
"""
End-to-end test: runs fetch_ica.py against the live Citrix environment
and validates that session.ica is downloaded successfully.

Reads credentials from .envrc in the project root.
Runs headless with CITRIX_DOWNLOAD_ONLY=true (skips Workspace launch).

Usage:
    python test_e2e.py
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent


def load_envrc(path: Path) -> dict:
    """Parse key=value pairs from a .envrc file (handles export and quoted values)."""
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^(?:export\s+)?(\w+)=["\']?(.*?)["\']?\s*$', line)
        if not m:
            continue
        env[m.group(1)] = m.group(2)
    return env


def main():
    envrc = ROOT / ".envrc"
    if not envrc.exists():
        print("ERROR: .envrc not found", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        env = {
            **os.environ,
            **load_envrc(envrc),
            "OUTPUT_DIR": tmp,
            "CITRIX_HEADLESS": "true",
            "CITRIX_DOWNLOAD_ONLY": "true",
        }

        print("=== Running fetch_ica.py ===")
        result = subprocess.run(
            [sys.executable, str(ROOT / "fetch_ica.py")],
            env=env,
        )

        print()
        ica = Path(tmp) / "session.ica"

        if result.returncode != 0:
            print(f"FAIL: fetch_ica.py exited with code {result.returncode}")
            sys.exit(1)

        if not ica.exists():
            print(f"FAIL: session.ica not found in {tmp}")
            sys.exit(1)

        if ica.stat().st_size == 0:
            print("FAIL: session.ica is empty")
            sys.exit(1)

        print(f"PASS: session.ica downloaded ({ica.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
