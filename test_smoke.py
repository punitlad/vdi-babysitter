"""
Smoke tests: validates vdi-babysitter help output against the binary on PATH.
No credentials or live environment required.
"""

import re
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("vdi-babysitter") is None,
    reason="vdi-babysitter not found on PATH",
)

BIN = "vdi-babysitter"


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"`{' '.join(cmd)}` exited {result.returncode}\n{result.stderr}"
    )
    return result.stdout + result.stderr


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
    output = _run([BIN, "version"])
    assert output.strip(), "version output was empty"
