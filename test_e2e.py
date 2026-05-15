"""
End-to-end test: runs `vdi-babysitter citrix connect --download-only`
against the live Citrix environment and validates that session.ica downloads.

Reads credentials from .envrc in the project root.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
_ENVRC = ROOT / ".envrc"


def _load_envrc(path: Path) -> dict:
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


@pytest.fixture(scope="module")
def cli() -> str:
    binary = shutil.which("vdi-babysitter")
    if not binary:
        pytest.skip("vdi-babysitter not found on PATH")
    return binary


@pytest.fixture(scope="module")
def envrc_vars() -> dict:
    if not _ENVRC.exists():
        pytest.skip(".envrc not found")
    return _load_envrc(_ENVRC)


def test_ica_download(cli, envrc_vars):
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            cli,
            "citrix", "connect",
            "--download-only",
            "--output-dir", tmp,
            "--log-level", "info",
        ]
        otp = envrc_vars.get("CITRIX_OTP")
        if otp:
            cmd += ["--otp", otp]

        result = subprocess.run(cmd, env={**os.environ, **envrc_vars})
        assert result.returncode == 0, f"vdi-babysitter exited {result.returncode}"

        ica = Path(tmp) / "session.ica"
        assert ica.exists(), f"session.ica not found in {tmp}"
        assert ica.stat().st_size > 0, "session.ica is empty"
