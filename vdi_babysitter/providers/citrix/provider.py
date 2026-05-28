"""Citrix provider: authentication, ICA download, session management."""

import logging
import os
import subprocess
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from vdi_babysitter.debug import DebugConfig, DebugSession, create_debug_session, prune_old_runs

log = logging.getLogger(__name__)


@dataclass
class CitrixConfig:
    storefront_url: str
    username: str
    password: str
    desktop_name: str = "My Windows 11 Desktop"
    pingid_url: str = "**/pingid/**"
    pingid_otp_text: str = "YubiKey"
    otp: Optional[str] = None
    otp_cmd: Optional[str] = None
    output_dir: Path = field(default_factory=lambda: Path.home() / ".vdi-babysitter" / "output")
    max_retries: int = 0
    restart_wait: int = 120
    restart_first: bool = False
    headless: bool = True
    download_only: bool = False
    timeout: Optional[int] = None


class CitrixProvider:
    def __init__(self, config: CitrixConfig, debug_config: Optional[DebugConfig] = None) -> None:
        self.config = config
        self._ica_file = config.output_dir / "session.ica"
        self._pending_downloads: list = []
        self._debug: Optional[DebugSession] = (
            create_debug_session(debug_config) if debug_config else None
        )

    def _pw(self, action: str) -> None:
        if self._debug:
            self._debug.record_action(action)

    def connect(self) -> None:
        """Full connect flow: auth → download ICA → launch Workspace → verify TCP."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.config.timeout if self.config.timeout else None
        dbg = self._debug

        if browser_path := os.environ.get("VDIBABYSITTER_PLAYWRIGHT_BROWSER_PATH"):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browser_path

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.config.headless,
                args=["--disable-external-protocol-dialog"],
                slow_mo=dbg.config.playwright_slow_mo if dbg else 0,
            )
            context = browser.new_context(accept_downloads=True)

            if dbg and dbg.config.playwright_trace:
                context.tracing.start(screenshots=True, snapshots=True, sources=True)

            page = context.new_page()
            page.on("download", lambda d: self._pending_downloads.append(d))
            page.on("response", self._log_launch_status)

            _outcome = "failed"
            _exc: Optional[Exception] = None
            _exc_tb: Optional[str] = None
            try:
                self._authenticate(page)

                if self.config.restart_first:
                    if dbg:
                        dbg.crumb("restart_first — restarting desktop before first attempt")
                    log.info("restart_first — restarting desktop before first attempt...")
                    self._restart_desktop(page, deadline=deadline)

                attempt = 0
                while True:
                    if deadline and time.time() > deadline:
                        raise RuntimeError(
                            f"Connect timed out after {self.config.timeout}s"
                        )

                    attempt += 1
                    if self.config.max_retries > 0 and attempt > self.config.max_retries:
                        raise RuntimeError(
                            f"Max retries ({self.config.max_retries}) reached without a successful connection"
                        )

                    attempt_label = f"attempt {attempt}" + (
                        f" of {self.config.max_retries}" if self.config.max_retries else ""
                    )
                    if dbg:
                        dbg.crumb(attempt_label)
                    log.info(
                        "=== Attempt %d%s ===",
                        attempt,
                        f" of {self.config.max_retries}" if self.config.max_retries else "",
                    )

                    self._pending_downloads.clear()

                    if not self._download_ica(page, deadline=deadline):
                        log.warning("Could not download ICA — restarting desktop and retrying...")
                        if dbg:
                            dbg.crumb("ICA download failed — restarting desktop")
                            dbg.retry()
                        self._restart_desktop(page, deadline=deadline)
                        continue

                    if self.config.download_only:
                        log.info("download_only — ICA saved, skipping Workspace launch.")
                        if dbg:
                            dbg.crumb("download_only — ICA saved, skipping Workspace launch")
                        _outcome = "success"
                        return

                    if dbg:
                        dbg.crumb("opening ICA with Citrix Workspace")
                    log.info("Opening ICA with Citrix Workspace...")
                    subprocess.run(["open", str(self._ica_file)], check=True)

                    if dbg:
                        dbg.crumb("verifying TCP connection")
                    if self._session_connected(timeout=45):
                        log.info("Citrix session established successfully.")
                        if dbg:
                            dbg.crumb("session established")
                        _outcome = "success"
                        return

                    log.warning("Session failed to connect — restarting desktop...")
                    if dbg:
                        dbg.crumb("TCP verification failed — restarting desktop")
                        dbg.retry()
                    self._restart_desktop(page, deadline=deadline)

            except Exception as exc:
                _exc = exc
                _exc_tb = traceback.format_exc()
                raise

            finally:
                if dbg:
                    page_url: Optional[str] = None
                    try:
                        page_url = page.url
                    except Exception:
                        pass

                    if _exc is not None and dbg.config.capture_screenshots:
                        try:
                            page.screenshot(path=str(dbg.run_dir / "screenshot.png"))
                        except Exception:
                            pass

                    if _exc is not None and dbg.config.capture_html:
                        try:
                            (dbg.run_dir / "page.html").write_text(page.content())
                        except Exception:
                            pass

                    if dbg.config.playwright_trace:
                        try:
                            context.tracing.stop(path=str(dbg.run_dir / "trace.zip"))
                        except Exception:
                            pass

                    dbg.write(
                        outcome=_outcome,
                        exc=_exc,
                        page_url=page_url if _exc else None,
                        exc_tb=_exc_tb,
                    )
                    prune_old_runs(dbg.run_dir.parent, dbg.config.keep_runs)

                browser.close()

    def _get_otp(self) -> str:
        if self.config.otp:
            log.info("Using OTP from --otp flag.")
            return self.config.otp

        if self.config.otp_cmd:
            log.info("Running --otp-cmd to get OTP...")
            result = subprocess.run(
                self.config.otp_cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=False,
            )
            otp = result.stdout.strip()
            if not otp:
                raise RuntimeError(
                    f"--otp-cmd produced no output (exit code {result.returncode})"
                )
            return otp

        log.info("Opening native OTP dialog — tap your YubiKey when prompted...")
        result = subprocess.run(
            [
                "osascript", "-e",
                'set otp to text returned of (display dialog "Tap your YubiKey now" '
                'default answer "" with title "VDI Babysitter" giving up after 60)\n'
                'return otp',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        otp = result.stdout.strip()
        if not otp:
            raise RuntimeError("OTP not received (dialog timed out or was cancelled)")
        return otp

    def _authenticate(self, page) -> None:
        dbg = self._debug
        if dbg:
            dbg.crumb("navigating to StoreFront")
        log.info("Navigating to StoreFront...")
        page.goto(self.config.storefront_url, wait_until="domcontentloaded")
        self._pw(f"goto {self.config.storefront_url}")

        log.info("Waiting for SSO login page...")
        page.wait_for_selector("input[type='password']", timeout=20_000)
        self._pw("wait_for_selector input[type='password']")

        for sel in [
            "input[name='username']",
            "input[id='username']",
            "input[type='email']",
            "input[type='text']",
        ]:
            if page.locator(sel).count() > 0:
                page.locator(sel).first.fill(self.config.username)
                self._pw(f"fill {sel}")
                break

        if dbg:
            dbg.crumb("submitting credentials")
        page.locator("input[type='password']").fill(self.config.password)
        self._pw("fill input[type='password']")
        log.info("Clicking Sign On...")
        page.locator("#signOnButton").click()
        self._pw("click #signOnButton")

        if dbg:
            dbg.crumb("waiting for PingID MFA redirect")
        log.info("Waiting for PingID MFA redirect...")
        page.wait_for_url(self.config.pingid_url, timeout=30_000)
        self._pw(f"wait_for_url {self.config.pingid_url}")

        log.info("Selecting OTP method...")
        page.get_by_text(self.config.pingid_otp_text, exact=False).first.click()
        self._pw(f"click '{self.config.pingid_otp_text}' OTP method")

        log.info("Clicking Sign On to proceed to OTP page...")
        page.locator("#device-submit").click()
        self._pw("click #device-submit")

        if dbg:
            dbg.crumb("waiting for OTP input")
        log.info("Waiting for OTP input field...")
        otp_field = page.wait_for_selector(
            "input[type='text']:visible, input[type='tel']:visible, input[type='password']:visible",
            timeout=15_000,
        )
        self._pw("wait_for_selector OTP input")

        otp = self._get_otp()
        if dbg:
            dbg.crumb("injecting OTP")
        log.info("OTP captured (%d chars) — injecting into page...", len(otp))
        otp_field.type(otp)
        self._pw("type OTP [redacted]")
        otp_field.press("Enter")
        self._pw("press Enter")

        # Check for OTP rejection before waiting for redirect.
        # PingID shows <div class="error-message show">Invalid passcode</div> on failure.
        time.sleep(2)
        error_el = page.locator(".error-message.show")
        if error_el.count() > 0:
            msg = error_el.first.inner_text().strip()
            raise RuntimeError(f"YubiKey OTP rejected by PingID: {msg!r}")

        if dbg:
            dbg.crumb("waiting for StoreFront redirect")
        log.info("Waiting for StoreFront redirect after auth...")
        storefront_host = self.config.storefront_url.split("//", 1)[1].split("/")[0]
        page.wait_for_url(f"**{storefront_host}**", timeout=60_000)
        self._pw(f"wait_for_url **{storefront_host}**")

        page.on("dialog", lambda d: d.dismiss())
        time.sleep(1)
        subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to key code 53'],
            check=False,
            capture_output=True,
        )

        try:
            page.get_by_text("Skip Check", exact=False).first.click(timeout=10_000)
            self._pw("click 'Skip Check'")
            log.info("Skipped endpoint analysis check.")
        except PlaywrightTimeoutError:
            log.info("No endpoint analysis check appeared — continuing.")

        page.wait_for_load_state("networkidle")
        if dbg:
            dbg.crumb("authentication complete")
        log.info("Authentication complete.")

    def _log_launch_status(self, response) -> None:
        """Background response listener — logs GetLaunchStatus polling state."""
        if "GetLaunchStatus" in response.url:
            try:
                body = response.json()
                log.debug(
                    "GetLaunchStatus: status=%s errorId=%s",
                    body.get("status"),
                    body.get("errorId"),
                )
            except Exception:
                pass

    def _is_terminal_launch_status(self, response) -> bool:
        """Predicate for wait_for_response — resolves only on success or failure."""
        if "GetLaunchStatus" not in response.url:
            return False
        try:
            return response.json().get("status") in ("success", "failure")
        except Exception:
            return False

    def _wait_for_download(self, page, deadline) -> bool:
        """Wait for the ICA download using Playwright's expect_download."""
        log.info("Waiting for ICA download to arrive...")
        # Check if download already landed in the listener before we got here.
        if self._pending_downloads:
            self._pending_downloads.pop(0).save_as(self._ica_file)
            log.info("ICA saved to %s", self._ica_file)
            return True
        remaining_ms = int((deadline - time.time()) * 1000) if deadline else 300_000
        try:
            with page.expect_download(timeout=remaining_ms) as dl_info:
                pass
            dl_info.value.save_as(self._ica_file)
            log.info("ICA saved to %s", self._ica_file)
            return True
        except PlaywrightTimeoutError:
            log.error("Timed out waiting for ICA download after GetLaunchStatus success.")
            return False

    def _download_ica(self, page, deadline=None) -> bool:
        remaining_ms = lambda: int((deadline - time.time()) * 1000) if deadline else 300_000

        page.wait_for_load_state("networkidle")

        # [1] Scenario 1: ICA already downloaded automatically on page load.
        if self._pending_downloads:
            log.info("Auto-download detected before Open click.")
            self._pending_downloads.pop(0).save_as(self._ica_file)
            log.info("ICA saved to %s", self._ica_file)
            return True

        restarted = False

        while True:
            # Open the action panel for the desktop.
            log.info("Opening action panel for '%s'...", self.config.desktop_name)
            page.get_by_text(self.config.desktop_name, exact=False).first.click()
            self._pw(f"click '{self.config.desktop_name}'")
            try:
                page.wait_for_selector(".appDetails-actions-header", timeout=5_000)
                self._pw("wait_for_selector .appDetails-actions-header")
            except PlaywrightTimeoutError:
                log.warning("Action panel did not appear — reloading...")
                self._pw("reload page (action panel timeout)")
                page.reload(wait_until="networkidle")
                if self._pending_downloads:
                    log.info("Auto-download detected after reload.")
                    self._pending_downloads.pop(0).save_as(self._ica_file)
                    log.info("ICA saved to %s", self._ica_file)
                    return True
                continue

            # Register listener before checking button state to avoid missing
            # responses that fire during the check or click.
            try:
                with page.expect_response(
                    self._is_terminal_launch_status, timeout=remaining_ms()
                ) as resp_info:
                    open_btn = page.locator(".appDetails-action-launch")
                    if not open_btn.evaluate("el => el.classList.contains('hidden')"):
                        log.info("Open button available — clicking...")
                        open_btn.click()
                        self._pw("click Open button")
                    else:
                        log.info(
                            "Open button greyed out — GetLaunchStatus polling in flight, "
                            "waiting for terminal response..."
                        )
                terminal = resp_info.value
            except PlaywrightTimeoutError:
                log.error("Timed out waiting for terminal GetLaunchStatus response.")
                return False

            body = terminal.json()
            status = body.get("status")
            log.info(
                "Terminal GetLaunchStatus: status=%s errorId=%s",
                status,
                body.get("errorId"),
            )

            if status == "success":
                return self._wait_for_download(page, deadline)

            # [5] Failure — Open button reactivates; click it for a retry.
            log.warning(
                "GetLaunchStatus failure (errorId=%s) — waiting for Open button to reactivate...",
                body.get("errorId"),
            )
            try:
                page.locator(".appDetails-action-launch:not(.hidden)").wait_for(
                    timeout=remaining_ms()
                )
            except PlaywrightTimeoutError:
                log.error("Open button did not reactivate after failure.")
                return False

            log.info("Open button reactivated — clicking for retry...")
            try:
                with page.expect_response(
                    self._is_terminal_launch_status, timeout=remaining_ms()
                ) as resp_info2:
                    page.locator(".appDetails-action-launch").click()
                terminal2 = resp_info2.value
            except PlaywrightTimeoutError:
                log.error("Timed out waiting for second terminal GetLaunchStatus response.")
                return False

            body2 = terminal2.json()
            status2 = body2.get("status")
            log.info(
                "Terminal GetLaunchStatus (retry): status=%s errorId=%s",
                status2,
                body2.get("errorId"),
            )

            if status2 == "success":
                return self._wait_for_download(page, deadline)

            # Second failure — restart once then loop back; give up if already restarted.
            if restarted:
                log.error("ICA download failed after restart — giving up.")
                return False

            log.warning("Second GetLaunchStatus failure — restarting desktop...")
            restarted = True
            self._restart_desktop(page, deadline=deadline)

            if self._pending_downloads:
                log.info("Auto-download detected after restart.")
                self._pending_downloads.pop(0).save_as(self._ica_file)
                log.info("ICA saved to %s", self._ica_file)
                return True

    def _restart_desktop(self, page, deadline=None) -> None:
        remaining_ms = int((deadline - time.time()) * 1000) if deadline else 300_000
        dbg = self._debug

        if dbg:
            dbg.crumb(f"restarting desktop '{self.config.desktop_name}'")
        log.info("Clicking '%s' → Restart...", self.config.desktop_name)
        page.get_by_text(self.config.desktop_name, exact=False).first.click()
        self._pw(f"click '{self.config.desktop_name}'")
        page.wait_for_selector(".appDetails-actions-header", timeout=5_000)
        self._pw("wait_for_selector .appDetails-actions-header")
        page.locator(".appDetails-action-restart").click()
        self._pw("click .appDetails-action-restart")

        log.info("Confirming restart dialog...")
        try:
            with page.expect_response(
                lambda r: "PowerOff" in r.url and r.json().get("status") == "success",
                timeout=remaining_ms,
            ):
                page.get_by_role("button", name="Restart").click()
                self._pw("click Restart confirmation")
        except PlaywrightTimeoutError:
            raise RuntimeError(
                "Timed out waiting for PowerOff to complete — "
                "PowerOff failure handling not yet implemented."
            )

        if dbg:
            dbg.crumb("PowerOff confirmed")
        log.info("PowerOff confirmed — GetLaunchStatus polling will resume automatically.")

    def _session_connected(self, timeout: int = 45) -> bool:
        log.info("Polling for established Citrix TCP connection (up to %ds)...", timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = subprocess.run(
                ["lsof", "-i", "-nP"],
                capture_output=True,
                text=True,
                check=False,
            )
            if "Citrix" in result.stdout and "ESTABLISHED" in result.stdout:
                return True
            time.sleep(3)
        return False
