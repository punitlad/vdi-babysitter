"""
Debug mode e2e tests — no live Citrix environment required.

Covers three error scenarios that can be validated through the CLI binary alone:
  1. VDI_BABYSITTER_DEBUG=1 with no debug.yaml  → hard fail with clear error
  2. VDI_BABYSITTER_DEBUG=1 with unknown key    → hard fail naming the bad key
  4. Connect failure without debug mode          → nudge toward VDI_BABYSITTER_DEBUG
     (inverse: debug mode active → nudge suppressed)
"""

import os
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


def _run(args: list[str], env: dict, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BIN] + args,
        capture_output=True,
        text=True,
        env=env,
        **kwargs,
    )


# ── Scenario 1: missing debug.yaml ─────────────────────────────────────────────

def test_debug_missing_yaml_exits_nonzero(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = _run(["version"], env=env)
    assert result.returncode != 0


def test_debug_missing_yaml_names_env_var(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = _run(["version"], env=env)
    assert "VDI_BABYSITTER_DEBUG" in result.stderr


def test_debug_missing_yaml_names_config_file(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = _run(["version"], env=env)
    assert "debug.yaml" in result.stderr


# ── Scenario 2: unknown key in debug.yaml ──────────────────────────────────────

def test_debug_unknown_key_exits_nonzero(tmp_path):
    debug_dir = tmp_path / ".vdi-babysitter"
    debug_dir.mkdir()
    (debug_dir / "debug.yaml").write_text("not_a_real_key: true\n")
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = _run(["version"], env=env)
    assert result.returncode != 0


def test_debug_unknown_key_names_offending_key(tmp_path):
    debug_dir = tmp_path / ".vdi-babysitter"
    debug_dir.mkdir()
    (debug_dir / "debug.yaml").write_text("not_a_real_key: true\n")
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = _run(["version"], env=env)
    assert "not_a_real_key" in result.stderr


def test_debug_unknown_key_lists_valid_keys(tmp_path):
    debug_dir = tmp_path / ".vdi-babysitter"
    debug_dir.mkdir()
    (debug_dir / "debug.yaml").write_text("bad_key: true\n")
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = _run(["version"], env=env)
    assert "Valid keys" in result.stderr


def test_debug_multiple_unknown_keys_all_named(tmp_path):
    debug_dir = tmp_path / ".vdi-babysitter"
    debug_dir.mkdir()
    (debug_dir / "debug.yaml").write_text("bad_key_one: true\nbad_key_two: false\n")
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = _run(["version"], env=env)
    assert "bad_key_one" in result.stderr
    assert "bad_key_two" in result.stderr


def test_debug_valid_yaml_proceeds_normally(tmp_path):
    debug_dir = tmp_path / ".vdi-babysitter"
    debug_dir.mkdir()
    (debug_dir / "debug.yaml").write_text(
        "playwright_trace: true\n"
        "capture_screenshots: false\n"
        "capture_html: false\n"
        "capture_locals: false\n"
        "keep_runs: 3\n"
    )
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = _run(["version"], env=env)
    assert result.returncode == 0


# ── Scenario 4: failure nudge ───────────────────────────────────────────────────

# Uses an unreachable storefront URL so the connect attempt fails immediately
# without needing the real Citrix environment. Playwright may or may not launch
# depending on browser availability — either way the exception propagates to the
# CLI and triggers the nudge path.

_BOGUS_CONNECT = [
    "citrix", "connect",
    "--storefront-url", "http://localhost:1",
    "--username", "testuser",
    "--password", "testpass",
    "--log-level", "quiet",
]


def test_connect_failure_exits_nonzero(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path)}
    env.pop("VDI_BABYSITTER_DEBUG", None)
    result = _run(_BOGUS_CONNECT, env=env)
    assert result.returncode != 0


def test_connect_failure_shows_nudge(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path)}
    env.pop("VDI_BABYSITTER_DEBUG", None)
    result = _run(_BOGUS_CONNECT, env=env)
    assert "VDI_BABYSITTER_DEBUG" in result.stderr
    assert "debug bundle" in result.stderr


def test_connect_failure_with_debug_suppresses_nudge(tmp_path):
    debug_dir = tmp_path / ".vdi-babysitter"
    debug_dir.mkdir()
    (debug_dir / "debug.yaml").write_text("playwright_trace: false\n")
    env = {**os.environ, "HOME": str(tmp_path), "VDI_BABYSITTER_DEBUG": "1"}
    result = _run(_BOGUS_CONNECT, env=env)
    assert result.returncode != 0
    assert "Tip: Re-run with VDI_BABYSITTER_DEBUG" not in result.stderr
