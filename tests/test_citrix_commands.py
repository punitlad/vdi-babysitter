"""Tests for vdi_babysitter/providers/citrix/commands.py"""

from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from vdi_babysitter.main import app

runner = CliRunner()

BASE_FLAGS = [
    "--storefront-url", "https://example.com",
    "--username", "user",
    "--password", "pass",
    "--otp", "123456",
]


# ── connect ────────────────────────────────────────────────────────────────────

_CITRIX_ENVVARS = (
    "CITRIX_STOREFRONT", "CITRIX_USER", "CITRIX_PASS",
    "CITRIX_APP", "CITRIX_PINGID_URL", "CITRIX_YUBIKEY_TEXT",
    "MAX_RETRIES", "RESTART_WAIT", "CITRIX_RESTART_FIRST",
    "CITRIX_DOWNLOAD_ONLY", "VDI_BABYSITTER_PROFILE",
)


def test_connect_missing_all_required(monkeypatch):
    for var in _CITRIX_ENVVARS:
        monkeypatch.delenv(var, raising=False)
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}):
        result = runner.invoke(app, ["citrix", "connect"])
    assert result.exit_code == 1
    assert "Missing required options" in result.output

def test_connect_missing_password(monkeypatch):
    for var in _CITRIX_ENVVARS:
        monkeypatch.delenv(var, raising=False)
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}):
        result = runner.invoke(app, ["citrix", "connect",
            "--storefront-url", "https://example.com", "--username", "user"])
    assert result.exit_code == 1
    assert "--password" in result.output

def test_connect_otp_and_otp_cmd_mutually_exclusive():
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}):
        result = runner.invoke(app, ["citrix", "connect",
            "--storefront-url", "https://example.com",
            "--username", "user", "--password", "pass",
            "--otp", "123", "--otp-cmd", "echo 123",
        ])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output

def test_connect_success():
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}), \
         patch("vdi_babysitter.providers.citrix.commands.CitrixProvider") as MockProvider:
        MockProvider.return_value.connect.return_value = None
        result = runner.invoke(app, ["citrix", "connect"] + BASE_FLAGS)
    assert result.exit_code == 0

def test_connect_output_json_on_success():
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}), \
         patch("vdi_babysitter.providers.citrix.commands.CitrixProvider") as MockProvider:
        MockProvider.return_value.connect.return_value = None
        result = runner.invoke(app, ["citrix", "connect"] + BASE_FLAGS + ["--output", "json"])
    assert result.exit_code == 0
    assert '"status": "connected"' in result.output

def test_connect_provider_error_shown_to_user():
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}), \
         patch("vdi_babysitter.providers.citrix.commands.CitrixProvider") as MockProvider:
        MockProvider.return_value.connect.side_effect = RuntimeError("YubiKey OTP rejected by PingID: 'Invalid passcode'")
        result = runner.invoke(app, ["citrix", "connect"] + BASE_FLAGS)
    assert result.exit_code == 1
    assert "YubiKey OTP rejected" in result.output

def test_connect_invalid_output_flag():
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}):
        result = runner.invoke(app, ["citrix", "connect"] + BASE_FLAGS + ["--output", "table"])
    assert result.exit_code == 1
    assert "--output" in result.output

def test_connect_invalid_log_level_flag():
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}):
        result = runner.invoke(app, ["citrix", "connect"] + BASE_FLAGS + ["--log-level", "verbose"])
    assert result.exit_code == 1
    assert "--log-level" in result.output

def test_connect_output_json_defaults_to_quiet_logging():
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}), \
         patch("vdi_babysitter.providers.citrix.commands.CitrixProvider") as MockProvider, \
         patch("vdi_babysitter.providers.citrix.commands._setup_logging") as mock_setup:
        MockProvider.return_value.connect.return_value = None
        runner.invoke(app, ["citrix", "connect"] + BASE_FLAGS + ["--output", "json"])
    mock_setup.assert_called_once_with("quiet")

def test_connect_output_json_with_explicit_log_level_debug():
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}), \
         patch("vdi_babysitter.providers.citrix.commands.CitrixProvider") as MockProvider, \
         patch("vdi_babysitter.providers.citrix.commands._setup_logging") as mock_setup:
        MockProvider.return_value.connect.return_value = None
        runner.invoke(app, ["citrix", "connect"] + BASE_FLAGS + ["--output", "json", "--log-level", "debug"])
    mock_setup.assert_called_once_with("debug")

def test_connect_debug_reraises():
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={}), \
         patch("vdi_babysitter.providers.citrix.commands.CitrixProvider") as MockProvider:
        MockProvider.return_value.connect.side_effect = RuntimeError("boom")
        result = runner.invoke(app, ["citrix", "connect"] + BASE_FLAGS + ["--log-level", "debug"])
    assert result.exception is not None
    assert "boom" in str(result.exception)

def test_connect_resolves_values_from_config(monkeypatch):
    for var in _CITRIX_ENVVARS:
        monkeypatch.delenv(var, raising=False)
    with patch("vdi_babysitter.providers.citrix.commands.get_active_profile", return_value="default"), \
         patch("vdi_babysitter.providers.citrix.commands.load_profile", return_value={
             "storefront_url": "https://from-config.com",
             "username": "config_user",
             "password": "config_pass",
         }), \
         patch("vdi_babysitter.providers.citrix.commands.CitrixProvider") as MockProvider:
        MockProvider.return_value.connect.return_value = None
        result = runner.invoke(app, ["citrix", "connect", "--otp", "123456"])
    assert result.exit_code == 0
    config_arg = MockProvider.call_args[0][0]
    assert config_arg.storefront_url == "https://from-config.com"


# ── disconnect ─────────────────────────────────────────────────────────────────

def test_disconnect_success():
    with patch("vdi_babysitter.providers.citrix.commands.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = runner.invoke(app, ["citrix", "disconnect"])
    assert result.exit_code == 0

def test_disconnect_no_session_found():
    with patch("vdi_babysitter.providers.citrix.commands.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        result = runner.invoke(app, ["citrix", "disconnect"])
    assert result.exit_code == 1
    assert "No active Citrix Workspace session" in result.output

def test_disconnect_output_json():
    with patch("vdi_babysitter.providers.citrix.commands.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = runner.invoke(app, ["citrix", "disconnect", "--output", "json"])
    assert result.exit_code == 0
    assert '"status": "disconnected"' in result.output


# ── status ─────────────────────────────────────────────────────────────────────

def test_status_connected():
    with patch("vdi_babysitter.providers.citrix.commands.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Citrix Workspace  ESTABLISHED"
        result = runner.invoke(app, ["citrix", "status"])
    assert result.exit_code == 0
    assert "connected" in result.output

def test_status_not_connected():
    with patch("vdi_babysitter.providers.citrix.commands.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "some other process"
        result = runner.invoke(app, ["citrix", "status"])
    assert result.exit_code == 1
    assert "not connected" in result.output

def test_status_json_connected():
    with patch("vdi_babysitter.providers.citrix.commands.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Citrix Workspace  ESTABLISHED"
        result = runner.invoke(app, ["citrix", "status", "--output", "json"])
    assert result.exit_code == 0
    assert '"connected": true' in result.output

def test_status_json_not_connected():
    with patch("vdi_babysitter.providers.citrix.commands.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        result = runner.invoke(app, ["citrix", "status", "--output", "json"])
    assert '"connected": false' in result.output
