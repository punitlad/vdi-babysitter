"""Tests for vdi_babysitter/debug.py"""

import time
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from vdi_babysitter.debug import (
    DebugConfig,
    DebugSession,
    create_debug_session,
    load_debug_config,
    prune_old_runs,
)


# --- load_debug_config ---

def test_no_env_var_returns_none(monkeypatch):
    monkeypatch.delenv("VDI_BABYSITTER_DEBUG", raising=False)
    assert load_debug_config() is None


def test_env_var_set_missing_file_exits(monkeypatch, tmp_path):
    monkeypatch.setenv("VDI_BABYSITTER_DEBUG", "1")
    missing = tmp_path / "debug.yaml"
    with pytest.raises(SystemExit):
        load_debug_config(debug_config_path=missing)


def test_env_var_set_valid_file_returns_config(monkeypatch, tmp_path):
    monkeypatch.setenv("VDI_BABYSITTER_DEBUG", "1")
    cfg = tmp_path / "debug.yaml"
    cfg.write_text(yaml.dump({"playwright_trace": False, "keep_runs": 3}))
    result = load_debug_config(debug_config_path=cfg)
    assert isinstance(result, DebugConfig)
    assert result.playwright_trace is False
    assert result.keep_runs == 3


def test_env_var_set_empty_file_uses_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("VDI_BABYSITTER_DEBUG", "1")
    cfg = tmp_path / "debug.yaml"
    cfg.write_text("")
    result = load_debug_config(debug_config_path=cfg)
    assert result == DebugConfig()


def test_env_var_set_unknown_key_exits(monkeypatch, tmp_path):
    monkeypatch.setenv("VDI_BABYSITTER_DEBUG", "1")
    cfg = tmp_path / "debug.yaml"
    cfg.write_text(yaml.dump({"playwright_trace": True, "not_a_real_key": True}))
    with pytest.raises(SystemExit):
        load_debug_config(debug_config_path=cfg)


def test_all_valid_keys_parse_correctly(monkeypatch, tmp_path):
    monkeypatch.setenv("VDI_BABYSITTER_DEBUG", "1")
    cfg = tmp_path / "debug.yaml"
    cfg.write_text(yaml.dump({
        "playwright_trace": True,
        "playwright_slow_mo": 500,
        "capture_screenshots": True,
        "capture_html": True,
        "keep_runs": 10,
    }))
    result = load_debug_config(debug_config_path=cfg)
    assert result == DebugConfig(
        playwright_trace=True,
        playwright_slow_mo=500,
        capture_screenshots=True,
        capture_html=True,
        keep_runs=10,
    )


# --- create_debug_session ---

def test_create_debug_session_creates_run_dir(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    assert session.run_dir.exists()
    assert session.run_dir.parent == tmp_path


def test_create_debug_session_timestamped_name(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    # directory name should look like 2026-05-28T14-30-00
    assert len(session.run_dir.name) == len("2026-05-28T14-30-00")


# --- DebugSession.write — success ---

def test_write_success_creates_artifacts(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.crumb("navigating to StoreFront")
    session.crumb("authentication complete")
    session.write(outcome="success")

    stats = (session.run_dir / "run_statistics.txt").read_text()
    assert "outcome:        success" in stats
    assert "duration_s:" in stats
    assert "vdi-babysitter:" in stats
    assert "python:" in stats
    assert "platform:" in stats

    flow = (session.run_dir / "orchestration_flow.txt").read_text()
    assert flow.startswith("CONNECTED")
    assert "navigating to StoreFront" in flow
    assert "authentication complete" in flow

    assert not (session.run_dir / "failure_block.txt").exists()


def test_write_success_tldr_printed_to_stderr(tmp_path, capsys):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.write(outcome="success")
    assert "CONNECTED" in capsys.readouterr().err


# --- DebugSession.write — failure ---

def test_write_failure_creates_failure_block(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.crumb("waiting for PingID MFA redirect")
    exc = RuntimeError("YubiKey OTP rejected")
    session.write(
        outcome="failed",
        exc=exc,
        page_url="https://pingid.example.com/mfa",
        exc_tb="Traceback (most recent call last):\n  ...\nRuntimeError: YubiKey OTP rejected",
    )

    block = (session.run_dir / "failure_block.txt").read_text()
    assert "waiting for PingID MFA redirect" in block
    assert "https://pingid.example.com/mfa" in block
    assert "RuntimeError: YubiKey OTP rejected" in block
    assert "Traceback" in block


def test_write_failure_tldr_includes_step_and_retries(tmp_path, capsys):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.crumb("verifying TCP connection")
    session.retry()
    session.retry()
    session.write(outcome="failed", exc=RuntimeError("timeout"))
    err = capsys.readouterr().err
    assert "FAILED at step 'verifying TCP connection'" in err
    assert "2 retries" in err


def test_write_failure_no_exc_tb_omits_traceback(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    exc = ValueError("bad value")
    session.write(outcome="failed", exc=exc)
    block = (session.run_dir / "failure_block.txt").read_text()
    assert "traceback:" not in block


def test_write_failure_unknown_url_when_none(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.write(outcome="failed", exc=RuntimeError("x"))
    block = (session.run_dir / "failure_block.txt").read_text()
    assert "url:   unknown" in block


# --- prune_old_runs ---

def _make_run_dirs(base: Path, count: int) -> list[Path]:
    dirs = []
    for i in range(count):
        d = base / f"run-{i:03d}"
        d.mkdir()
        # space mtime apart so sort is deterministic
        os.utime(d, (i, i))
        dirs.append(d)
    return dirs


import os


def test_prune_keeps_newest(tmp_path):
    dirs = _make_run_dirs(tmp_path, 7)
    prune_old_runs(tmp_path, keep_runs=3)
    remaining = sorted(tmp_path.iterdir(), key=lambda p: p.stat().st_mtime)
    assert len(remaining) == 3
    # the three newest (highest mtime) should survive
    assert set(remaining) == set(dirs[-3:])


def test_prune_no_op_when_under_limit(tmp_path):
    dirs = _make_run_dirs(tmp_path, 3)
    prune_old_runs(tmp_path, keep_runs=5)
    assert len(list(tmp_path.iterdir())) == 3


def test_prune_nonexistent_dir_is_noop(tmp_path):
    prune_old_runs(tmp_path / "nonexistent", keep_runs=3)  # should not raise


def test_prune_zero_keep_runs_is_noop(tmp_path):
    _make_run_dirs(tmp_path, 3)
    prune_old_runs(tmp_path, keep_runs=0)
    assert len(list(tmp_path.iterdir())) == 3


# --- manifest.json ---

def test_write_success_creates_manifest(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.crumb("navigating to StoreFront")
    session.crumb("authentication complete")
    session.write(outcome="success")

    import json
    manifest = json.loads((session.run_dir / "manifest.json").read_text())
    assert manifest["outcome"] == "success"
    assert manifest["retries"] == 0
    assert manifest["failed_at_step"] is None
    assert any("authentication complete" in e for e in manifest["orchestration_flow"])
    assert "tldr" in manifest
    assert manifest["tldr"].startswith("CONNECTED")


def test_write_failure_manifest_has_failed_step(tmp_path):
    import json
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.crumb("verifying TCP connection")
    session.write(outcome="failed", exc=RuntimeError("timeout"))

    manifest = json.loads((session.run_dir / "manifest.json").read_text())
    assert manifest["outcome"] == "failed"
    assert manifest["failed_at_step"] == "verifying TCP connection"
    assert manifest["tldr"].startswith("FAILED")
    assert any("verifying TCP connection" in e for e in manifest["orchestration_flow"])


def test_manifest_contains_version_info(tmp_path):
    import json
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.write(outcome="success")

    manifest = json.loads((session.run_dir / "manifest.json").read_text())
    assert "vdi_babysitter" in manifest
    assert "python" in manifest
    assert "platform" in manifest
    assert isinstance(manifest["duration_s"], float)


# --- capture_locals ---

def test_write_failure_with_capture_locals_includes_locals(tmp_path):
    config = DebugConfig(capture_locals=True)
    session = create_debug_session(config, base_dir=tmp_path)

    def _raise():
        local_var = "sensitive"
        raise RuntimeError("locals test")

    try:
        _raise()
    except RuntimeError as exc:
        session.write(outcome="failed", exc=exc, exc_tb="ignored when capture_locals is on")

    block = (session.run_dir / "failure_block.txt").read_text()
    assert "traceback (with locals):" in block
    assert "local_var" in block
    assert "traceback:" not in block.replace("traceback (with locals):", "")


def test_write_failure_without_capture_locals_uses_exc_tb(tmp_path):
    config = DebugConfig(capture_locals=False)
    session = create_debug_session(config, base_dir=tmp_path)
    try:
        raise ValueError("plain tb test")
    except ValueError as exc:
        session.write(
            outcome="failed",
            exc=exc,
            exc_tb="Traceback (most recent call last):\n  ...\nValueError: plain tb test",
        )

    block = (session.run_dir / "failure_block.txt").read_text()
    assert "traceback:" in block
    assert "traceback (with locals):" not in block


def test_capture_locals_parsed_from_yaml(monkeypatch, tmp_path):
    monkeypatch.setenv("VDI_BABYSITTER_DEBUG", "1")
    cfg = tmp_path / "debug.yaml"
    cfg.write_text("capture_locals: true\n")
    result = load_debug_config(debug_config_path=cfg)
    assert result.capture_locals is True


# --- playwright actions ---

def test_record_action_appends_with_timestamp(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.record_action("click #signOnButton")
    session.record_action("fill input[type='password']")
    assert len(session._pw_actions) == 2
    assert "click #signOnButton" in session._pw_actions[0]
    assert "fill input[type='password']" in session._pw_actions[1]
    # timestamps present — format HH:MM:SS.mmm
    assert session._pw_actions[0].startswith("[")


def test_write_failure_includes_playwright_actions(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.record_action("goto https://citrix.example.com")
    session.record_action("click #signOnButton")
    session.write(outcome="failed", exc=RuntimeError("boom"))

    block = (session.run_dir / "failure_block.txt").read_text()
    assert "playwright actions:" in block
    assert "goto https://citrix.example.com" in block
    assert "click #signOnButton" in block


def test_write_success_omits_playwright_actions_from_failure_block(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.record_action("goto https://citrix.example.com")
    session.write(outcome="success")
    assert not (session.run_dir / "failure_block.txt").exists()


def test_write_failure_no_actions_omits_section(tmp_path):
    config = DebugConfig()
    session = create_debug_session(config, base_dir=tmp_path)
    session.write(outcome="failed", exc=RuntimeError("no actions"))

    block = (session.run_dir / "failure_block.txt").read_text()
    assert "playwright actions:" not in block


# --- post-failure re-run prompt ---

def test_failure_prints_trace_command_when_trace_enabled(tmp_path, capsys):
    config = DebugConfig(playwright_trace=True)
    session = create_debug_session(config, base_dir=tmp_path)
    session.write(outcome="failed", exc=RuntimeError("x"))
    err = capsys.readouterr().err
    assert "playwright show-trace" in err
    assert "trace.zip" in err


def test_failure_no_trace_command_when_trace_disabled(tmp_path, capsys):
    config = DebugConfig(playwright_trace=False)
    session = create_debug_session(config, base_dir=tmp_path)
    session.write(outcome="failed", exc=RuntimeError("x"))
    err = capsys.readouterr().err
    assert "playwright show-trace" not in err


def test_failure_hints_for_disabled_capture_options(tmp_path, capsys):
    config = DebugConfig(capture_screenshots=False, capture_html=False, capture_locals=False)
    session = create_debug_session(config, base_dir=tmp_path)
    session.write(outcome="failed", exc=RuntimeError("x"))
    err = capsys.readouterr().err
    assert "capture_screenshots" in err
    assert "capture_html" in err
    assert "capture_locals" in err


def test_failure_no_hints_when_all_captures_enabled(tmp_path, capsys):
    config = DebugConfig(
        playwright_trace=False,
        capture_screenshots=True,
        capture_html=True,
        capture_locals=True,
    )
    session = create_debug_session(config, base_dir=tmp_path)
    session.write(outcome="failed", exc=RuntimeError("x"))
    err = capsys.readouterr().err
    assert "capture_screenshots" not in err
    assert "capture_html" not in err
    assert "capture_locals" not in err


def test_success_prints_no_hints(tmp_path, capsys):
    config = DebugConfig(capture_screenshots=False, capture_html=False, capture_locals=False)
    session = create_debug_session(config, base_dir=tmp_path)
    session.write(outcome="success")
    err = capsys.readouterr().err
    assert "capture_screenshots" not in err
    assert "playwright show-trace" not in err
