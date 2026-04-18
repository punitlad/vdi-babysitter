"""Tests for vdi_babysitter/config.py"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from vdi_babysitter.config import (
    get_active_profile,
    list_profiles,
    load_profile,
    resolve,
    set_active_profile,
    write_profile,
)


# ── resolve ────────────────────────────────────────────────────────────────────

def test_resolve_flag_wins():
    assert resolve("flag", "config", "default") == "flag"

def test_resolve_config_wins_when_no_flag():
    assert resolve(None, "config", "default") == "config"

def test_resolve_default_when_neither():
    assert resolve(None, None, "default") == "default"

def test_resolve_none_default():
    assert resolve(None, None) is None

def test_resolve_falsy_flag_not_overridden():
    # 0 and False are valid flag values, not "missing"
    assert resolve(0, "config", "default") == 0
    assert resolve(False, "config", "default") is False


# ── get_active_profile ─────────────────────────────────────────────────────────

def test_get_active_profile_flag_wins():
    assert get_active_profile("myflag") == "myflag"

def test_get_active_profile_env_var(monkeypatch):
    monkeypatch.setenv("VDI_BABYSITTER_PROFILE", "myenv")
    assert get_active_profile() == "myenv"

def test_get_active_profile_flag_overrides_env(monkeypatch):
    monkeypatch.setenv("VDI_BABYSITTER_PROFILE", "myenv")
    assert get_active_profile("myflag") == "myflag"

def test_get_active_profile_current_file(tmp_path, monkeypatch):
    monkeypatch.delenv("VDI_BABYSITTER_PROFILE", raising=False)
    current_file = tmp_path / "current_profile"
    current_file.write_text("saved_profile")
    with patch("vdi_babysitter.config.CURRENT_PROFILE_FILE", current_file):
        assert get_active_profile() == "saved_profile"

def test_get_active_profile_empty_file_falls_to_default(tmp_path, monkeypatch):
    monkeypatch.delenv("VDI_BABYSITTER_PROFILE", raising=False)
    current_file = tmp_path / "current_profile"
    current_file.write_text("   ")
    with patch("vdi_babysitter.config.CURRENT_PROFILE_FILE", current_file):
        assert get_active_profile() == "default"

def test_get_active_profile_no_file_returns_default(tmp_path, monkeypatch):
    monkeypatch.delenv("VDI_BABYSITTER_PROFILE", raising=False)
    with patch("vdi_babysitter.config.CURRENT_PROFILE_FILE", tmp_path / "no_file"):
        assert get_active_profile() == "default"


# ── set_active_profile ─────────────────────────────────────────────────────────

def test_set_active_profile_writes_file(tmp_path):
    current_file = tmp_path / "current_profile"
    with patch("vdi_babysitter.config.CONFIG_DIR", tmp_path), \
         patch("vdi_babysitter.config.CURRENT_PROFILE_FILE", current_file):
        set_active_profile("myprofile")
    assert current_file.read_text() == "myprofile"

def test_set_active_profile_creates_dir(tmp_path):
    config_dir = tmp_path / "nested" / "dir"
    current_file = config_dir / "current_profile"
    with patch("vdi_babysitter.config.CONFIG_DIR", config_dir), \
         patch("vdi_babysitter.config.CURRENT_PROFILE_FILE", current_file):
        set_active_profile("work")
    assert current_file.read_text() == "work"


# ── load_profile ───────────────────────────────────────────────────────────────

def _write_config(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data))


def test_load_profile_no_config_file(tmp_path):
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", tmp_path / "config.yaml"), \
         patch("vdi_babysitter.config.LOCAL_CONFIG", tmp_path / "local.yaml"):
        assert load_profile("default") == {}

def test_load_profile_returns_data(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg, {"profiles": {"default": {"storefront_url": "https://example.com"}}})
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg), \
         patch("vdi_babysitter.config.LOCAL_CONFIG", tmp_path / "local.yaml"):
        result = load_profile("default")
    assert result["storefront_url"] == "https://example.com"

def test_load_profile_missing_profile_returns_empty(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg, {"profiles": {"other": {"storefront_url": "https://other.com"}}})
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg), \
         patch("vdi_babysitter.config.LOCAL_CONFIG", tmp_path / "local.yaml"):
        assert load_profile("default") == {}

def test_load_profile_unknown_key_exits(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg, {"profiles": {"default": {"totally_invalid_key": "value"}}})
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg), \
         patch("vdi_babysitter.config.LOCAL_CONFIG", tmp_path / "local.yaml"):
        with pytest.raises(SystemExit):
            load_profile("default")

def test_load_profile_local_config_takes_precedence(tmp_path):
    local = tmp_path / "local.yaml"
    _write_config(local, {"profiles": {"default": {"storefront_url": "https://local.com"}}})
    glob = tmp_path / "global.yaml"
    _write_config(glob, {"profiles": {"default": {"storefront_url": "https://global.com"}}})
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", glob), \
         patch("vdi_babysitter.config.LOCAL_CONFIG", local):
        assert load_profile("default")["storefront_url"] == "https://local.com"

def test_load_profile_empty_yaml(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("")
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg), \
         patch("vdi_babysitter.config.LOCAL_CONFIG", tmp_path / "local.yaml"):
        assert load_profile("default") == {}

def test_load_profile_non_dict_profile_skipped(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg, {"profiles": {"default": None, "work": {"storefront_url": "https://work.com"}}})
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg), \
         patch("vdi_babysitter.config.LOCAL_CONFIG", tmp_path / "local.yaml"):
        assert load_profile("work")["storefront_url"] == "https://work.com"


# ── write_profile ──────────────────────────────────────────────────────────────

def test_write_profile_creates_file(tmp_path):
    cfg = tmp_path / "config.yaml"
    with patch("vdi_babysitter.config.CONFIG_DIR", tmp_path), \
         patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg):
        write_profile("default", {"storefront_url": "https://example.com"})
    raw = yaml.safe_load(cfg.read_text())
    assert raw["profiles"]["default"]["storefront_url"] == "https://example.com"

def test_write_profile_updates_existing(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg, {"profiles": {"default": {"storefront_url": "https://old.com"}}})
    with patch("vdi_babysitter.config.CONFIG_DIR", tmp_path), \
         patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg):
        write_profile("default", {"storefront_url": "https://new.com"})
    raw = yaml.safe_load(cfg.read_text())
    assert raw["profiles"]["default"]["storefront_url"] == "https://new.com"

def test_write_profile_preserves_other_profiles(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg, {"profiles": {"work": {"storefront_url": "https://work.com"}}})
    with patch("vdi_babysitter.config.CONFIG_DIR", tmp_path), \
         patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg):
        write_profile("personal", {"storefront_url": "https://personal.com"})
    raw = yaml.safe_load(cfg.read_text())
    assert "work" in raw["profiles"]
    assert "personal" in raw["profiles"]

def test_write_profile_returns_path(tmp_path):
    cfg = tmp_path / "config.yaml"
    with patch("vdi_babysitter.config.CONFIG_DIR", tmp_path), \
         patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg):
        result = write_profile("default", {})
    assert result == cfg


# ── list_profiles ──────────────────────────────────────────────────────────────

def test_list_profiles_no_file(tmp_path):
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", tmp_path / "config.yaml"):
        assert list_profiles() == []

def test_list_profiles_returns_names(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg, {"profiles": {"default": {}, "work": {}}})
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg):
        assert set(list_profiles()) == {"default", "work"}

def test_list_profiles_empty_profiles(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg, {"profiles": {}})
    with patch("vdi_babysitter.config.GLOBAL_CONFIG", cfg):
        assert list_profiles() == []
