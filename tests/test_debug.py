"""Tests for vdi_babysitter/debug.py"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from vdi_babysitter.debug import DebugConfig, load_debug_config


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
