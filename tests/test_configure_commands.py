"""Tests for vdi_babysitter/configure_commands.py"""

from pathlib import Path
from unittest.mock import patch
from typer.testing import CliRunner
from vdi_babysitter.main import app

runner = CliRunner()


# ── configure set ──────────────────────────────────────────────────────────────

def test_configure_set_valid_key(tmp_path):
    cfg = tmp_path / "config.yaml"
    with patch("vdi_babysitter.configure_commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.configure_commands.load_profile", return_value={}), \
         patch("vdi_babysitter.configure_commands.write_profile", return_value=cfg) as mock_write:
        result = runner.invoke(app, ["configure", "set", "storefront_url", "https://example.com"])
    assert result.exit_code == 0
    mock_write.assert_called_once_with("default", {"storefront_url": "https://example.com"})

def test_configure_set_invalid_key():
    result = runner.invoke(app, ["configure", "set", "not_a_real_key", "value"])
    assert result.exit_code == 1
    assert "not a valid config key" in result.output

def test_configure_set_with_profile_flag(tmp_path):
    cfg = tmp_path / "config.yaml"
    with patch("vdi_babysitter.configure_commands.get_active_profile", return_value="work"), \
         patch("vdi_babysitter.configure_commands.load_profile", return_value={}), \
         patch("vdi_babysitter.configure_commands.write_profile", return_value=cfg) as mock_write:
        result = runner.invoke(app, ["configure", "set", "username", "myuser", "--profile", "work"])
    assert result.exit_code == 0
    mock_write.assert_called_once_with("work", {"username": "myuser"})

def test_configure_set_merges_with_existing(tmp_path):
    cfg = tmp_path / "config.yaml"
    existing = {"storefront_url": "https://example.com"}
    with patch("vdi_babysitter.configure_commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.configure_commands.load_profile", return_value=existing), \
         patch("vdi_babysitter.configure_commands.write_profile", return_value=cfg) as mock_write:
        result = runner.invoke(app, ["configure", "set", "username", "myuser"])
    assert result.exit_code == 0
    written = mock_write.call_args[0][1]
    assert written["storefront_url"] == "https://example.com"
    assert written["username"] == "myuser"


# ── configure show ─────────────────────────────────────────────────────────────

def test_configure_show_displays_values():
    with patch("vdi_babysitter.configure_commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.configure_commands.load_profile", return_value={
             "storefront_url": "https://example.com",
             "username": "myuser",
         }):
        result = runner.invoke(app, ["configure", "show"])
    assert result.exit_code == 0
    assert "storefront_url" in result.output
    assert "https://example.com" in result.output

def test_configure_show_masks_password():
    with patch("vdi_babysitter.configure_commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.configure_commands.load_profile", return_value={"password": "secret123"}):
        result = runner.invoke(app, ["configure", "show"])
    assert result.exit_code == 0
    assert "secret123" not in result.output
    assert "********" in result.output

def test_configure_show_empty_profile_exits_1():
    with patch("vdi_babysitter.configure_commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.configure_commands.load_profile", return_value={}):
        result = runner.invoke(app, ["configure", "show"])
    assert result.exit_code == 1

def test_configure_show_with_profile_flag():
    with patch("vdi_babysitter.configure_commands.get_active_profile", return_value="work") as mock_get, \
         patch("vdi_babysitter.configure_commands.load_profile", return_value={"username": "workuser"}):
        result = runner.invoke(app, ["configure", "show", "--profile", "work"])
    assert result.exit_code == 0
    mock_get.assert_called_once_with("work")


# ── configure list-profiles ────────────────────────────────────────────────────

def test_configure_list_profiles_shows_names():
    with patch("vdi_babysitter.configure_commands.list_profiles", return_value=["default", "work"]):
        result = runner.invoke(app, ["configure", "list-profiles"])
    assert result.exit_code == 0
    assert "default" in result.output
    assert "work" in result.output

def test_configure_list_profiles_empty_exits_1():
    with patch("vdi_babysitter.configure_commands.list_profiles", return_value=[]):
        result = runner.invoke(app, ["configure", "list-profiles"])
    assert result.exit_code == 1


# ── configure wizard ───────────────────────────────────────────────────────────

def test_configure_wizard_saves_profile(tmp_path):
    cfg = tmp_path / "config.yaml"
    inputs = "\n".join([
        "https://example.com",  # storefront_url
        "myuser",               # username
        "mypass",               # password
        "",                     # desktop_name (keep default)
        "",                     # pingid_url (keep default)
        "",                     # pingid_otp_text (keep default)
        "",                     # otp_cmd (skip)
        "",                     # output_dir (keep default)
        "",                     # max_retries (keep default)
        "",                     # restart_wait (keep default)
        "",                     # timeout (skip)
        "",                     # restart_first (keep default)
        "",                     # download_only (keep default)
        "",                     # no_headless (keep default)
    ]) + "\n"
    with patch("vdi_babysitter.configure_commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.configure_commands.load_profile", return_value={}), \
         patch("vdi_babysitter.configure_commands.write_profile", return_value=cfg) as mock_write:
        result = runner.invoke(app, ["configure"], input=inputs)
    assert result.exit_code == 0
    written = mock_write.call_args[0][1]
    assert written["storefront_url"] == "https://example.com"
    assert written["username"] == "myuser"
