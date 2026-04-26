"""Tests for vdi_babysitter/providers/citrix/provider.py"""

import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from vdi_babysitter.providers.citrix.provider import CitrixConfig, CitrixProvider


# ── CitrixConfig defaults ──────────────────────────────────────────────────────

def test_citrix_config_defaults():
    cfg = CitrixConfig(storefront_url="https://x.com", username="u", password="p")
    assert cfg.desktop_name == "My Windows 11 Desktop"
    assert cfg.pingid_url == "**/pingid/**"
    assert cfg.pingid_otp_text == "YubiKey"
    assert cfg.headless is True
    assert cfg.max_retries == 0
    assert cfg.restart_wait == 120
    assert cfg.restart_first is False
    assert cfg.download_only is False
    assert cfg.otp is None
    assert cfg.otp_cmd is None
    assert cfg.timeout is None

def test_citrix_config_custom_output_dir(tmp_path):
    cfg = CitrixConfig(storefront_url="x", username="u", password="p", output_dir=tmp_path)
    assert cfg.output_dir == tmp_path


# ── _get_otp ───────────────────────────────────────────────────────────────────

def make_provider(**kwargs):
    defaults = dict(storefront_url="https://x.com", username="u", password="p")
    defaults.update(kwargs)
    return CitrixProvider(CitrixConfig(**defaults))

def test_get_otp_from_flag():
    provider = make_provider(otp="myotp123")
    assert provider._get_otp() == "myotp123"

def test_get_otp_from_cmd(tmp_path):
    provider = make_provider(otp_cmd="echo freshotp")
    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "freshotp\n"
        mock_run.return_value.returncode = 0
        result = provider._get_otp()
    assert result == "freshotp"
    assert mock_run.call_args[1]["shell"] is True

def test_get_otp_cmd_empty_output_raises():
    provider = make_provider(otp_cmd="exit 1")
    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 1
        with pytest.raises(RuntimeError, match="no output"):
            provider._get_otp()


# ── _session_connected ─────────────────────────────────────────────────────────

def test_session_connected_returns_true_when_citrix_established():
    provider = make_provider()
    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Citrix Workspace  TCP ESTABLISHED"
        assert provider._session_connected(timeout=5) is True

def test_session_connected_returns_false_on_timeout():
    provider = make_provider()
    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run") as mock_run, \
         patch("vdi_babysitter.providers.citrix.provider.time.sleep"), \
         patch("vdi_babysitter.providers.citrix.provider.time.time", side_effect=[0, 0, 50]):
        mock_run.return_value.stdout = "some other stuff"
        assert provider._session_connected(timeout=10) is False

def test_session_connected_no_citrix_process():
    provider = make_provider()
    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run") as mock_run, \
         patch("vdi_babysitter.providers.citrix.provider.time.sleep"), \
         patch("vdi_babysitter.providers.citrix.provider.time.time", side_effect=[0, 0, 50]):
        mock_run.return_value.stdout = "ESTABLISHED but no citrix"
        assert provider._session_connected(timeout=10) is False


# ── _restart_desktop ───────────────────────────────────────────────────────────

def test_restart_desktop_clicks_and_waits():
    provider = make_provider(restart_wait=0)
    page = MagicMock()

    with patch("vdi_babysitter.providers.citrix.provider.time.sleep") as mock_sleep:
        provider._restart_desktop(page)

    page.get_by_text.assert_called()
    page.locator(".appDetails-action-restart").click.assert_called_once()
    page.get_by_role("button", name="Restart").click.assert_called_once()
    mock_sleep.assert_called()


# ── _download_ica ──────────────────────────────────────────────────────────────

def test_download_ica_uses_pending_download(tmp_path):
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()

    fake_download = MagicMock()
    provider._pending_downloads = [fake_download]

    with patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        result = provider._download_ica(page)

    assert result is True
    fake_download.save_as.assert_called_once_with(tmp_path / "session.ica")

def test_download_ica_clicks_open_button(tmp_path):
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    open_btn = MagicMock()
    open_btn.evaluate.return_value = False  # not hidden
    page.locator.return_value = open_btn

    fake_download = MagicMock()
    page.expect_download.return_value.__enter__ = MagicMock(return_value=MagicMock(value=fake_download))
    page.expect_download.return_value.__exit__ = MagicMock(return_value=False)

    with patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        result = provider._download_ica(page)

    assert result is True

def test_download_ica_returns_false_after_all_attempts(tmp_path):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

    with patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        result = provider._download_ica(page)

    assert result is False


def _get_response_handler(page):
    """Extract the handler registered via page.on('response', handler)."""
    calls = [c for c in page.on.call_args_list if c[0][0] == "response"]
    assert calls, "No 'response' listener registered"
    return calls[0][0][1]


def test_download_ica_registers_response_listener(tmp_path):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []
    page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

    with patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        provider._download_ica(page)

    assert _get_response_handler(page) is not None


def test_download_ica_response_listener_logs_get_launch_status(tmp_path):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []
    page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

    with patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        provider._download_ica(page)

    handler = _get_response_handler(page)

    mock_response = MagicMock()
    mock_response.url = "https://citrix.example.com/Citrix/AppStoreWeb/Resources/GetLaunchStatus/abc123"
    mock_response.json.return_value = {"status": "retry", "fileFetchUrl": None, "pollTimeout": 5}

    with patch("vdi_babysitter.providers.citrix.provider.log") as mock_log:
        handler(mock_response)
        mock_log.debug.assert_called_once()
        assert "retry" in str(mock_log.debug.call_args)


def test_download_ica_response_listener_logs_failure_with_error_id(tmp_path):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []
    page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

    with patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        provider._download_ica(page)

    handler = _get_response_handler(page)

    mock_response = MagicMock()
    mock_response.url = "https://citrix.example.com/Citrix/AppStoreWeb/Resources/GetLaunchStatus/abc123"
    mock_response.json.return_value = {"status": "failure", "errorId": "UnavailableDesktop", "fileFetchUrl": None}

    with patch("vdi_babysitter.providers.citrix.provider.log") as mock_log:
        handler(mock_response)
        mock_log.debug.assert_called_once()
        assert "UnavailableDesktop" in str(mock_log.debug.call_args)


def test_download_ica_response_listener_ignores_other_urls(tmp_path):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []
    page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

    with patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        provider._download_ica(page)

    handler = _get_response_handler(page)

    mock_response = MagicMock()
    mock_response.url = "https://citrix.example.com/Citrix/AppStoreWeb/Resources/LaunchIca/abc.ica"

    with patch("vdi_babysitter.providers.citrix.provider.log") as mock_log:
        handler(mock_response)
        mock_log.debug.assert_not_called()


def test_download_ica_response_listener_swallows_json_error(tmp_path):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []
    page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

    with patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        provider._download_ica(page)

    handler = _get_response_handler(page)

    mock_response = MagicMock()
    mock_response.url = "https://citrix.example.com/Citrix/AppStoreWeb/Resources/GetLaunchStatus/abc123"
    mock_response.json.side_effect = Exception("parse error")

    # Should not raise
    handler(mock_response)


# ── _authenticate ──────────────────────────────────────────────────────────────

def test_authenticate_otp_rejection_raises():
    provider = make_provider(otp="badotp")
    page = MagicMock()

    # OTP field mock
    otp_field = MagicMock()
    page.wait_for_selector.return_value = otp_field

    # Error element present after submit
    error_el = MagicMock()
    error_el.count.return_value = 1
    error_el.first.inner_text.return_value = "Invalid passcode"
    page.locator.return_value = error_el

    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run"), \
         patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        with pytest.raises(RuntimeError, match="Invalid passcode"):
            provider._authenticate(page)

def test_authenticate_completes_successfully():
    provider = make_provider(otp="validotp")
    page = MagicMock()

    otp_field = MagicMock()
    page.wait_for_selector.return_value = otp_field

    # No error element
    error_el = MagicMock()
    error_el.count.return_value = 0

    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    skip_btn = MagicMock()
    skip_btn.first.click.side_effect = PlaywrightTimeoutError("no skip button")

    def locator_side_effect(selector):
        if "error-message" in selector:
            return error_el
        mock = MagicMock()
        mock.count.return_value = 0
        return mock

    page.locator.side_effect = locator_side_effect
    page.get_by_text.return_value.first.click.side_effect = [
        None,       # pingid_otp_text click
        PlaywrightTimeoutError("no skip"),  # Skip Check
    ]

    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run"), \
         patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        # Should not raise
        provider._authenticate(page)


# ── connect orchestration ──────────────────────────────────────────────────────

def test_connect_download_only_exits_after_ica(tmp_path):
    provider = make_provider(output_dir=tmp_path, download_only=True, otp="otp123")

    fake_download = MagicMock()
    fake_download.save_as = MagicMock()

    mock_page = MagicMock()
    mock_page.locator.return_value.count.return_value = 0  # no error element
    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_download_ica", return_value=True), \
         patch("vdi_babysitter.providers.citrix.provider.subprocess.run"), \
         patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        provider.connect()  # should return without raising

def test_connect_raises_on_max_retries(tmp_path):
    provider = make_provider(output_dir=tmp_path, max_retries=2, otp="otp123")

    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_download_ica", return_value=False), \
         patch.object(provider, "_restart_desktop"), \
         patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        with pytest.raises(RuntimeError, match="Max retries"):
            provider.connect()

def test_connect_timeout_raises(tmp_path):
    provider = make_provider(output_dir=tmp_path, timeout=1, otp="otp123")

    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    # Patch helpers so no internal logging calls consume time.time() values.
    # Sequence: [0] for deadline calc, [0] first loop check (no timeout yet),
    # [999] second loop check (past deadline → raise).
    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_download_ica", return_value=False), \
         patch.object(provider, "_restart_desktop"), \
         patch("vdi_babysitter.providers.citrix.provider.time.time", side_effect=[0, 0, 999, 999]), \
         patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        with pytest.raises(RuntimeError, match="timed out"):
            provider.connect()
