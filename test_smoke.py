"""
Smoke tests: validates vdi-babysitter help output against the binary on PATH.
No credentials or live environment required.
"""

import os
import re
import shutil
import subprocess

import pytest

BIN = os.environ.get("VDI_BABYSITTER_CMD", "vdi-babysitter")

pytestmark = pytest.mark.skipif(
    shutil.which(BIN) is None,
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
    assert "--storefront-url" in output
    assert "--otp" in output
    assert "--otp-cmd" in output
    assert "--download-only" in output
    assert "--max-retries" in output
    assert "--restart-first" in output
    assert "--output" in output
    assert "--log-level" in output


def test_citrix_disconnect_help():
    output = _run([BIN, "citrix", "disconnect", "--help"])
    assert "--output" in output
    assert "--log-level" in output


def test_citrix_status_help():
    output = _run([BIN, "citrix", "status", "--help"])
    assert "--watch" in output
    assert "--interval" in output


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
