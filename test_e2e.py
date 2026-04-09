#!/usr/bin/env python3
"""
End-to-end test: runs `vdi-babysitter citrix connect --download-only`
against the live Citrix environment and validates that session.ica downloads.

Reads credentials from .envrc in the project root.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
CLI = ROOT / ".venv" / "bin" / "vdi-babysitter"


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

    envrc_vars = load_envrc(envrc)

    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, **envrc_vars}

        cmd = [
            str(CLI),
            "citrix", "connect",
            "--download-only",
            "--output-dir", tmp,
            "--verbose",
        ]

        # Pass OTP explicitly if set in .envrc (CITRIX_OTP → --otp flag,
        # since OTP is no longer read from env vars by the CLI).
        otp = envrc_vars.get("CITRIX_OTP")
        if otp:
            cmd += ["--otp", otp]

        print(f"=== Running: {' '.join(cmd)} ===")
        result = subprocess.run(cmd, env=env)

        print()
        ica = Path(tmp) / "session.ica"

        if result.returncode != 0:
            print(f"FAIL: vdi-babysitter exited with code {result.returncode}")
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
