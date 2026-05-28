"""Tests for vdi_babysitter/providers/citrix/provider.py"""

import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from vdi_babysitter.providers.citrix.provider import CitrixConfig, CitrixProvider
from vdi_babysitter.debug import DebugConfig, create_debug_session


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

def test_restart_desktop_waits_for_poweroff_response():
    provider = make_provider()
    page = MagicMock()

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock())
    cm.__exit__ = MagicMock(return_value=False)
    page.expect_response.return_value = cm

    provider._restart_desktop(page)

    page.get_by_text.assert_called()
    page.locator(".appDetails-action-restart").click.assert_called_once()
    page.get_by_role("button", name="Restart").click.assert_called_once()
    page.expect_response.assert_called_once()

def test_restart_desktop_raises_on_poweroff_timeout():
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider()
    page = MagicMock()

    cm = MagicMock()
    cm.__enter__ = MagicMock(side_effect=PlaywrightTimeoutError("timeout"))
    cm.__exit__ = MagicMock(return_value=False)
    page.expect_response.return_value = cm

    with pytest.raises(RuntimeError, match="PowerOff"):
        provider._restart_desktop(page)


# ── _log_launch_status ─────────────────────────────────────────────────────────

def make_response(url, json_body=None, json_error=None):
    r = MagicMock()
    r.url = url
    if json_error:
        r.json.side_effect = json_error
    else:
        r.json.return_value = json_body or {}
    return r

LAUNCH_STATUS_URL = "https://citrix.example.com/Citrix/AppStoreWeb/Resources/GetLaunchStatus/abc"
OTHER_URL = "https://citrix.example.com/Citrix/AppStoreWeb/Resources/LaunchIca/abc.ica"

def test_log_launch_status_logs_status_and_error_id():
    provider = make_provider()
    response = make_response(LAUNCH_STATUS_URL, {"status": "retry", "errorId": None})
    with patch("vdi_babysitter.providers.citrix.provider.log") as mock_log:
        provider._log_launch_status(response)
        mock_log.debug.assert_called_once()
        assert "retry" in str(mock_log.debug.call_args)

def test_log_launch_status_logs_failure_with_error_id():
    provider = make_provider()
    response = make_response(LAUNCH_STATUS_URL, {"status": "failure", "errorId": "UnavailableDesktop"})
    with patch("vdi_babysitter.providers.citrix.provider.log") as mock_log:
        provider._log_launch_status(response)
        mock_log.debug.assert_called_once()
        assert "UnavailableDesktop" in str(mock_log.debug.call_args)

def test_log_launch_status_ignores_other_urls():
    provider = make_provider()
    response = make_response(OTHER_URL)
    with patch("vdi_babysitter.providers.citrix.provider.log") as mock_log:
        provider._log_launch_status(response)
        mock_log.debug.assert_not_called()

def test_log_launch_status_swallows_json_error():
    provider = make_provider()
    response = make_response(LAUNCH_STATUS_URL, json_error=Exception("bad json"))
    provider._log_launch_status(response)  # must not raise


# ── _is_terminal_launch_status ─────────────────────────────────────────────────

def test_is_terminal_returns_true_for_success():
    provider = make_provider()
    assert provider._is_terminal_launch_status(
        make_response(LAUNCH_STATUS_URL, {"status": "success"})
    ) is True

def test_is_terminal_returns_true_for_failure():
    provider = make_provider()
    assert provider._is_terminal_launch_status(
        make_response(LAUNCH_STATUS_URL, {"status": "failure", "errorId": "UnavailableDesktop"})
    ) is True

def test_is_terminal_returns_false_for_retry():
    provider = make_provider()
    assert provider._is_terminal_launch_status(
        make_response(LAUNCH_STATUS_URL, {"status": "retry"})
    ) is False

def test_is_terminal_returns_false_for_non_launch_status_url():
    provider = make_provider()
    assert provider._is_terminal_launch_status(make_response(OTHER_URL, {"status": "success"})) is False

def test_is_terminal_returns_false_on_json_error():
    provider = make_provider()
    assert provider._is_terminal_launch_status(
        make_response(LAUNCH_STATUS_URL, json_error=Exception("bad"))
    ) is False


# ── _download_ica ──────────────────────────────────────────────────────────────

def _make_terminal_response(status, error_id=None):
    body = {"status": status}
    if error_id:
        body["errorId"] = error_id
    return make_response(LAUNCH_STATUS_URL, body)


def _make_expect_response_cm(response=None, timeout_error=False):
    """Build a mock context manager for page.expect_response."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    cm = MagicMock()
    resp_info = MagicMock()
    if timeout_error:
        cm.__enter__ = MagicMock(side_effect=PlaywrightTimeoutError("timeout"))
    else:
        resp_info.value = response
        cm.__enter__ = MagicMock(return_value=resp_info)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def test_download_ica_scenario1_auto_download_on_entry(tmp_path):
    """Scenario 1: ICA already in _pending_downloads when _download_ica is called."""
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    fake_dl = MagicMock()
    provider._pending_downloads = [fake_dl]

    result = provider._download_ica(page)

    assert result is True
    fake_dl.save_as.assert_called_once_with(tmp_path / "session.ica")
    page.expect_response.assert_not_called()


def test_download_ica_scenario2_greyed_out_then_success(tmp_path):
    """Scenario 2: Open button greyed out, GetLaunchStatus → success, download arrives."""
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    open_btn = MagicMock()
    open_btn.evaluate.return_value = True  # hidden
    page.locator.return_value = open_btn

    terminal = _make_terminal_response("success")
    page.expect_response.return_value = _make_expect_response_cm(terminal)

    with patch.object(provider, "_wait_for_download", return_value=True) as mock_wait:
        result = provider._download_ica(page)

    assert result is True
    open_btn.click.assert_not_called()
    mock_wait.assert_called_once()


def test_download_ica_scenario2_open_available_then_success(tmp_path):
    """Scenario 2: Open button clickable, click it, GetLaunchStatus → success."""
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    open_btn = MagicMock()
    open_btn.evaluate.return_value = False  # not hidden
    page.locator.return_value = open_btn

    terminal = _make_terminal_response("success")
    page.expect_response.return_value = _make_expect_response_cm(terminal)

    with patch.object(provider, "_wait_for_download", return_value=True):
        result = provider._download_ica(page)

    assert result is True
    open_btn.click.assert_called_once()


def test_download_ica_scenario3_failure_then_retry_success(tmp_path):
    """Scenario 3: first GetLaunchStatus failure, Open reactivates, retry → success."""
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    open_btn = MagicMock()
    open_btn.evaluate.return_value = False
    page.locator.return_value = open_btn

    failure = _make_terminal_response("failure", "UnavailableDesktop")
    success = _make_terminal_response("success")
    page.expect_response.side_effect = [
        _make_expect_response_cm(failure),
        _make_expect_response_cm(success),
    ]

    with patch.object(provider, "_wait_for_download", return_value=True):
        result = provider._download_ica(page)

    assert result is True
    assert page.expect_response.call_count == 2


def test_download_ica_scenario3_failure_retry_failure_then_restart_and_success(tmp_path):
    """Scenario 3 → restart: two failures trigger restart; success on next loop."""
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    open_btn = MagicMock()
    open_btn.evaluate.return_value = False
    page.locator.return_value = open_btn

    failure = _make_terminal_response("failure", "UnavailableDesktop")
    success = _make_terminal_response("success")
    # First iteration: two failures → restart; second iteration: success
    page.expect_response.side_effect = [
        _make_expect_response_cm(failure),
        _make_expect_response_cm(failure),
        _make_expect_response_cm(success),
    ]

    fake_dl = MagicMock()

    def inject_download_after_restart(p, **kwargs):
        provider._pending_downloads.append(fake_dl)

    with patch.object(provider, "_restart_desktop", side_effect=inject_download_after_restart), \
         patch.object(provider, "_wait_for_download", return_value=True):
        result = provider._download_ica(page)

    assert result is True


def test_download_ica_gives_up_after_second_restart_failure(tmp_path):
    """After restart, if two more failures occur, return False."""
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    open_btn = MagicMock()
    open_btn.evaluate.return_value = False
    page.locator.return_value = open_btn

    failure = _make_terminal_response("failure", "UnavailableDesktop")
    page.expect_response.side_effect = [
        _make_expect_response_cm(failure),
        _make_expect_response_cm(failure),
        _make_expect_response_cm(failure),
        _make_expect_response_cm(failure),
    ]

    with patch.object(provider, "_restart_desktop"):
        result = provider._download_ica(page)

    assert result is False


def test_download_ica_returns_false_on_expect_response_timeout(tmp_path):
    """If expect_response times out on first wait, return False."""
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    open_btn = MagicMock()
    open_btn.evaluate.return_value = False
    page.locator.return_value = open_btn

    page.expect_response.return_value = _make_expect_response_cm(timeout_error=True)

    result = provider._download_ica(page)

    assert result is False


def test_download_ica_returns_false_when_open_button_does_not_reactivate(tmp_path):
    """If Open button doesn't reactivate after failure, return False."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    open_btn = MagicMock()
    open_btn.evaluate.return_value = False

    reactivate_btn = MagicMock()
    reactivate_btn.wait_for.side_effect = PlaywrightTimeoutError("timeout")
    page.locator.side_effect = [open_btn, reactivate_btn, open_btn]

    failure = _make_terminal_response("failure", "UnavailableDesktop")
    page.expect_response.return_value = _make_expect_response_cm(failure)

    result = provider._download_ica(page)

    assert result is False


def test_download_ica_auto_download_after_reload(tmp_path):
    """If action panel times out and auto-download arrives after reload, return True."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    page = MagicMock()
    provider._pending_downloads = []

    fake_dl = MagicMock()

    def inject_download(*args, **kwargs):
        provider._pending_downloads.append(fake_dl)

    page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")
    page.reload.side_effect = inject_download

    result = provider._download_ica(page)

    assert result is True
    fake_dl.save_as.assert_called_once_with(tmp_path / "session.ica")


# ── _wait_for_download ─────────────────────────────────────────────────────────

def test_wait_for_download_returns_true_when_download_already_pending(tmp_path):
    provider = make_provider(output_dir=tmp_path)
    fake_dl = MagicMock()
    provider._pending_downloads = [fake_dl]
    page = MagicMock()

    result = provider._wait_for_download(page, deadline=None)

    assert result is True
    fake_dl.save_as.assert_called_once_with(tmp_path / "session.ica")
    page.expect_download.assert_not_called()

def test_wait_for_download_uses_expect_download_when_no_pending(tmp_path):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    provider._pending_downloads = []
    page = MagicMock()

    fake_dl = MagicMock()
    cm = MagicMock()
    dl_info = MagicMock()
    dl_info.value = fake_dl
    cm.__enter__ = MagicMock(return_value=dl_info)
    cm.__exit__ = MagicMock(return_value=False)
    page.expect_download.return_value = cm

    result = provider._wait_for_download(page, deadline=None)

    assert result is True
    fake_dl.save_as.assert_called_once_with(tmp_path / "session.ica")

def test_wait_for_download_returns_false_on_timeout(tmp_path):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    provider = make_provider(output_dir=tmp_path)
    provider._pending_downloads = []
    page = MagicMock()

    cm = MagicMock()
    cm.__enter__ = MagicMock(side_effect=PlaywrightTimeoutError("timeout"))
    cm.__exit__ = MagicMock(return_value=False)
    page.expect_download.return_value = cm

    result = provider._wait_for_download(page, deadline=None)

    assert result is False


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


def test_connect_sets_playwright_browser_path(tmp_path, monkeypatch):
    monkeypatch.setenv("VDIBABYSITTER_PLAYWRIGHT_BROWSER_PATH", "/custom/browsers")
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    provider = make_provider(output_dir=tmp_path, download_only=True, otp="otp123")

    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    import os
    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_download_ica", return_value=True):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        provider.connect()

    assert os.environ.get("PLAYWRIGHT_BROWSERS_PATH") == "/custom/browsers"


# ── _get_otp native dialog ─────────────────────────────────────────────────────

def test_get_otp_native_dialog_calls_osascript():
    provider = make_provider()  # no otp, no otp_cmd
    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "myotp\n"
        mock_run.return_value.returncode = 0
        result = provider._get_otp()
    assert result == "myotp"
    cmd = mock_run.call_args[0][0]
    assert "osascript" in cmd


def test_get_otp_native_dialog_empty_raises():
    provider = make_provider()
    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0
        with pytest.raises(RuntimeError, match="OTP not received"):
            provider._get_otp()


# ── connect with debug session ─────────────────────────────────────────────────

def _inject_debug(provider, tmp_path, **config_kwargs):
    config = DebugConfig(**config_kwargs)
    session = create_debug_session(config, base_dir=tmp_path / "debug")
    provider._debug = session
    return session


def _make_connect_mocks():
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context
    return mock_page, mock_context, mock_browser


def test_connect_with_debug_success_writes_artifacts(tmp_path):
    provider = make_provider(output_dir=tmp_path, download_only=True, otp="otp123")
    session = _inject_debug(provider, tmp_path, playwright_trace=False)
    _, _, mock_browser = _make_connect_mocks()
    mock_browser.new_context.return_value.new_page.return_value = MagicMock()

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_download_ica", return_value=True), \
         patch("vdi_babysitter.providers.citrix.provider.prune_old_runs"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        provider.connect()

    assert (session.run_dir / "run_statistics.txt").exists()
    assert (session.run_dir / "orchestration_flow.txt").exists()
    assert not (session.run_dir / "failure_block.txt").exists()
    stats = (session.run_dir / "run_statistics.txt").read_text()
    assert "outcome:        success" in stats


def test_connect_with_debug_failure_writes_failure_block(tmp_path):
    provider = make_provider(output_dir=tmp_path, otp="otp123")
    session = _inject_debug(provider, tmp_path, playwright_trace=False)
    _, _, mock_browser = _make_connect_mocks()
    mock_browser.new_context.return_value.new_page.return_value = MagicMock()

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate", side_effect=RuntimeError("auth failed")), \
         patch("vdi_babysitter.providers.citrix.provider.prune_old_runs"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        with pytest.raises(RuntimeError, match="auth failed"):
            provider.connect()

    assert (session.run_dir / "failure_block.txt").exists()
    block = (session.run_dir / "failure_block.txt").read_text()
    assert "auth failed" in block


def test_connect_with_debug_playwright_trace_start_stop(tmp_path):
    provider = make_provider(output_dir=tmp_path, download_only=True, otp="otp123")
    session = _inject_debug(provider, tmp_path, playwright_trace=True)
    mock_page, mock_context, mock_browser = _make_connect_mocks()

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_download_ica", return_value=True), \
         patch("vdi_babysitter.providers.citrix.provider.prune_old_runs"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        provider.connect()

    mock_context.tracing.start.assert_called_once()
    mock_context.tracing.stop.assert_called_once()
    stop_path = mock_context.tracing.stop.call_args[1]["path"]
    assert stop_path.endswith("trace.zip")


def test_connect_with_debug_capture_screenshot_on_failure(tmp_path):
    provider = make_provider(output_dir=tmp_path, otp="otp123")
    session = _inject_debug(provider, tmp_path, playwright_trace=False, capture_screenshots=True)
    mock_page, mock_context, mock_browser = _make_connect_mocks()

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate", side_effect=RuntimeError("fail")), \
         patch("vdi_babysitter.providers.citrix.provider.prune_old_runs"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        with pytest.raises(RuntimeError):
            provider.connect()

    mock_page.screenshot.assert_called_once()
    assert "screenshot.png" in mock_page.screenshot.call_args[1]["path"]


def test_connect_with_debug_capture_html_on_failure(tmp_path):
    provider = make_provider(output_dir=tmp_path, otp="otp123")
    session = _inject_debug(provider, tmp_path, playwright_trace=False, capture_html=True)
    mock_page, mock_context, mock_browser = _make_connect_mocks()
    mock_page.content.return_value = "<html></html>"

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate", side_effect=RuntimeError("fail")), \
         patch("vdi_babysitter.providers.citrix.provider.prune_old_runs"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        with pytest.raises(RuntimeError):
            provider.connect()

    mock_page.content.assert_called_once()
    assert (session.run_dir / "page.html").exists()


def test_connect_with_debug_restart_first_adds_crumb(tmp_path):
    provider = make_provider(output_dir=tmp_path, restart_first=True, download_only=True, otp="otp123")
    session = _inject_debug(provider, tmp_path, playwright_trace=False)
    _, _, mock_browser = _make_connect_mocks()

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_restart_desktop"), \
         patch.object(provider, "_download_ica", return_value=True), \
         patch("vdi_babysitter.providers.citrix.provider.prune_old_runs"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        provider.connect()

    crumb_steps = [c for c in session._crumbs if "restart_first" in c]
    assert crumb_steps


def test_connect_with_debug_download_failure_increments_retry(tmp_path):
    provider = make_provider(output_dir=tmp_path, max_retries=1, otp="otp123")
    session = _inject_debug(provider, tmp_path, playwright_trace=False)
    _, _, mock_browser = _make_connect_mocks()

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_download_ica", return_value=False), \
         patch.object(provider, "_restart_desktop"), \
         patch("vdi_babysitter.providers.citrix.provider.prune_old_runs"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        with pytest.raises(RuntimeError, match="Max retries"):
            provider.connect()

    assert session._retries >= 1
    crumbs = " ".join(session._crumbs)
    assert "ICA download failed" in crumbs


def test_connect_with_debug_session_tcp_success(tmp_path):
    provider = make_provider(output_dir=tmp_path, otp="otp123")
    session = _inject_debug(provider, tmp_path, playwright_trace=False)
    _, _, mock_browser = _make_connect_mocks()

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_download_ica", return_value=True), \
         patch.object(provider, "_session_connected", return_value=True), \
         patch("vdi_babysitter.providers.citrix.provider.subprocess.run"), \
         patch("vdi_babysitter.providers.citrix.provider.prune_old_runs"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        provider.connect()

    crumbs = " ".join(session._crumbs)
    assert "session established" in crumbs
    assert "opening ICA" in crumbs
    assert "verifying TCP" in crumbs


def test_connect_with_debug_tcp_fail_then_restart(tmp_path):
    """TCP verification fails once → restart → max retries triggers."""
    provider = make_provider(output_dir=tmp_path, max_retries=1, otp="otp123")
    session = _inject_debug(provider, tmp_path, playwright_trace=False)
    _, _, mock_browser = _make_connect_mocks()

    with patch("vdi_babysitter.providers.citrix.provider.sync_playwright") as mock_pw, \
         patch.object(provider, "_authenticate"), \
         patch.object(provider, "_download_ica", return_value=True), \
         patch.object(provider, "_session_connected", return_value=False), \
         patch.object(provider, "_restart_desktop"), \
         patch("vdi_babysitter.providers.citrix.provider.subprocess.run"), \
         patch("vdi_babysitter.providers.citrix.provider.prune_old_runs"):
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        with pytest.raises(RuntimeError, match="Max retries"):
            provider.connect()

    crumbs = " ".join(session._crumbs)
    assert "TCP verification failed" in crumbs
    assert session._retries >= 1


# ── _authenticate with debug ────────────────────────────────────────────────────

def test_authenticate_with_debug_adds_crumbs(tmp_path):
    provider = make_provider(otp="validotp")
    session = _inject_debug(provider, tmp_path, playwright_trace=False)

    page = MagicMock()
    otp_field = MagicMock()
    page.wait_for_selector.return_value = otp_field

    error_el = MagicMock()
    error_el.count.return_value = 0

    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    def locator_side_effect(selector):
        if "error-message" in selector:
            return error_el
        m = MagicMock()
        m.count.return_value = 0
        return m

    page.locator.side_effect = locator_side_effect
    page.get_by_text.return_value.first.click.side_effect = [
        None,
        PlaywrightTimeoutError("no skip"),
    ]

    with patch("vdi_babysitter.providers.citrix.provider.subprocess.run"), \
         patch("vdi_babysitter.providers.citrix.provider.time.sleep"):
        provider._authenticate(page)

    crumbs = " ".join(session._crumbs)
    assert "navigating to StoreFront" in crumbs
    assert "submitting credentials" in crumbs
    assert "authentication complete" in crumbs


# ── _restart_desktop with debug ────────────────────────────────────────────────

def test_restart_desktop_with_debug_adds_crumbs(tmp_path):
    provider = make_provider()
    session = _inject_debug(provider, tmp_path, playwright_trace=False)

    page = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock())
    cm.__exit__ = MagicMock(return_value=False)
    page.expect_response.return_value = cm

    provider._restart_desktop(page)

    crumbs = " ".join(session._crumbs)
    assert "restarting desktop" in crumbs
    assert "PowerOff confirmed" in crumbs
