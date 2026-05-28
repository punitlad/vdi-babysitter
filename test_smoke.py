"""
Smoke tests: validates vdi-babysitter help output against the binary on PATH.
No credentials or live environment required.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent
_VENV_BIN = _ROOT / ".venv" / "bin" / "vdi-babysitter"
BIN = os.environ.get(
    "VDI_BABYSITTER_CMD",
    str(_VENV_BIN) if _VENV_BIN.exists() else "vdi-babysitter",
)

pytestmark = pytest.mark.skipif(
    not Path(BIN).exists() and shutil.which(BIN) is None,
    reason=f"vdi-babysitter binary not found: {BIN}",
)


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"`{' '.join(cmd)}` exited {result.returncode}\n{result.stderr}"
    )
    output = result.stdout + result.stderr
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def test_no_args_shows_error_and_help():
    r = subprocess.run([BIN], capture_output=True, text=True)
    combined = r.stdout + r.stderr
    assert r.returncode != 0
    assert "Error: command argument required." in combined
    assert "citrix" in combined
    assert "configure" in combined
    assert "use" in combined


def test_help():
    output = _run([BIN, "--help"])
    assert "citrix" in output
    assert "configure" in output
    assert "use" in output


def test_citrix_connect_help():
    output = _run([BIN, "citrix", "connect", "--help"])
    assert "Global Options" in output
    before, after = output.split("Global Options", 1)
    # command-specific options in Options panel
    for flag in ("--storefront-url", "--otp", "--otp-cmd", "--download-only",
                 "--max-retries", "--restart-first", "--timeout"):
        assert flag in before, f"{flag} should be in Options, not Global Options"
    # global options in Global Options panel — use trailing space to avoid
    # matching --output as a prefix of --output-dir in the Options panel
    for flag in ("--profile", "--output", "--log-level"):
        assert f"{flag} " in after, f"{flag} should be in Global Options"
        assert f"{flag} " not in before, f"{flag} should not be in Options"


def test_citrix_disconnect_help():
    output = _run([BIN, "citrix", "disconnect", "--help"])
    assert "Global Options" in output
    _, after = output.split("Global Options", 1)
    for flag in ("--profile", "--output", "--log-level"):
        assert flag in after, f"{flag} should be in Global Options"


def test_citrix_status_help():
    output = _run([BIN, "citrix", "status", "--help"])
    assert "Global Options" in output
    before, after = output.split("Global Options", 1)
    for flag in ("--watch", "--interval"):
        assert flag in before, f"{flag} should be in Options, not Global Options"
    for flag in ("--profile", "--output", "--log-level"):
        assert f"{flag} " in after, f"{flag} should be in Global Options"
        assert f"{flag} " not in before, f"{flag} should not be in Options"


def test_version():
    _run([BIN, "version"])


# ── debug mode ─────────────────────────────────────────────────────────────────

def test_debug_env_var_not_in_help():
    output = _run([BIN, "--help"])
    assert "VDI_BABYSITTER_DEBUG" not in output


def test_debug_env_var_without_file_fails(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = subprocess.run([BIN, "version"], capture_output=True, text=True, env=env)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "VDI_BABYSITTER_DEBUG" in combined
    assert "debug.yaml" in combined


def test_debug_env_var_with_valid_file_proceeds(tmp_path):
    debug_dir = tmp_path / ".vdi-babysitter"
    debug_dir.mkdir()
    (debug_dir / "debug.yaml").write_text("playwright_trace: true\nkeep_runs: 3\n")
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = subprocess.run([BIN, "version"], capture_output=True, text=True, env=env)
    assert result.returncode == 0
