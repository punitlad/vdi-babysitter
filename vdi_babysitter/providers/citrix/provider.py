"""Citrix provider: authentication, ICA download, session management."""

import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

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
    def __init__(self, config: CitrixConfig) -> None:
        self.config = config
        self._ica_file = config.output_dir / "session.ica"
        self._pending_downloads: list = []

    def connect(self) -> None:
        """Full connect flow: auth → download ICA → launch Workspace → verify TCP."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.config.timeout if self.config.timeout else None

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.config.headless,
                args=["--disable-external-protocol-dialog"],
            )
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.on("download", lambda d: self._pending_downloads.append(d))

            try:
                self._authenticate(page)

                if self.config.restart_first:
                    log.info("restart_first — restarting desktop before first attempt...")
                    self._restart_desktop(page)

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

                    log.info(
                        "=== Attempt %d%s ===",
                        attempt,
                        f" of {self.config.max_retries}" if self.config.max_retries else "",
                    )

                    self._pending_downloads.clear()

                    if not self._download_ica(page):
                        log.warning("Could not download ICA — restarting desktop and retrying...")
                        self._restart_desktop(page)
                        continue

                    if self.config.download_only:
                        log.info("download_only — ICA saved, skipping Workspace launch.")
                        return

                    log.info("Opening ICA with Citrix Workspace...")
                    subprocess.run(["open", str(self._ica_file)], check=True)

                    if self._session_connected(timeout=45):
                        log.info("Citrix session established successfully.")
                        return

                    log.warning("Session failed to connect — restarting desktop...")
                    self._restart_desktop(page)

            finally:
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
        log.info("Navigating to StoreFront...")
        page.goto(self.config.storefront_url, wait_until="domcontentloaded")

        log.info("Waiting for SSO login page...")
        page.wait_for_selector("input[type='password']", timeout=20_000)

        for sel in [
            "input[name='username']",
            "input[id='username']",
            "input[type='email']",
            "input[type='text']",
        ]:
            if page.locator(sel).count() > 0:
                page.locator(sel).first.fill(self.config.username)
                break

        page.locator("input[type='password']").fill(self.config.password)
        log.info("Clicking Sign On...")
        page.locator("#signOnButton").click()

        log.info("Waiting for PingID MFA redirect...")
        page.wait_for_url(self.config.pingid_url, timeout=30_000)

        log.info("Selecting OTP method...")
        page.get_by_text(self.config.pingid_otp_text, exact=False).first.click()

        log.info("Clicking Sign On to proceed to OTP page...")
        page.locator("#device-submit").click()

        log.info("Waiting for OTP input field...")
        otp_field = page.wait_for_selector(
            "input[type='text']:visible, input[type='tel']:visible, input[type='password']:visible",
            timeout=15_000,
        )

        otp = self._get_otp()
        log.info("OTP captured (%d chars) — injecting into page...", len(otp))
        otp_field.type(otp)
        otp_field.press("Enter")

        # Check for OTP rejection before waiting for redirect.
        # PingID shows <div class="error-message show">Invalid passcode</div> on failure.
        time.sleep(2)
        error_el = page.locator(".error-message.show")
        if error_el.count() > 0:
            msg = error_el.first.inner_text().strip()
            raise RuntimeError(f"YubiKey OTP rejected by PingID: {msg!r}")

        log.info("Waiting for StoreFront redirect after auth...")
        storefront_host = self.config.storefront_url.split("//", 1)[1].split("/")[0]
        page.wait_for_url(f"**{storefront_host}**", timeout=60_000)

        page.on("dialog", lambda d: d.dismiss())
        time.sleep(1)
        subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to key code 53'],
            check=False,
            capture_output=True,
        )

        try:
            page.get_by_text("Skip Check", exact=False).first.click(timeout=10_000)
            log.info("Skipped endpoint analysis check.")
        except PlaywrightTimeoutError:
            log.info("No endpoint analysis check appeared — continuing.")

        page.wait_for_load_state("networkidle")
        log.info("Authentication complete.")

    def _download_ica(self, page) -> bool:
        page.wait_for_load_state("networkidle")
        time.sleep(5)

        if self._pending_downloads:
            log.info("Auto-download detected.")
            self._pending_downloads.pop(0).save_as(self._ica_file)
            log.info("ICA saved to %s", self._ica_file)
            return True

        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            log.info(
                "Opening action panel for '%s' (attempt %d/%d)...",
                self.config.desktop_name,
                attempt,
                max_attempts,
            )
            page.get_by_text(self.config.desktop_name, exact=False).first.click()

            try:
                page.wait_for_selector(".appDetails-actions-header", timeout=5_000)
            except PlaywrightTimeoutError:
                log.warning("Action panel did not appear — refreshing...")
                page.reload(wait_until="networkidle")
                continue

            open_btn = page.locator(".appDetails-action-launch")
            if open_btn.evaluate("el => el.classList.contains('hidden')"):
                log.warning("'Open' not available yet — refreshing and retrying...")
                page.reload(wait_until="networkidle")
                time.sleep(3)
                continue

            try:
                with page.expect_download(timeout=15_000) as dl_info:
                    open_btn.click()
                dl_info.value.save_as(self._ica_file)
                log.info("ICA saved to %s", self._ica_file)
                return True
            except PlaywrightTimeoutError:
                log.warning("Download timed out after clicking Open — retrying...")
                page.reload(wait_until="networkidle")

        log.error("'Open' remained unavailable after %d attempts.", max_attempts)
        return False

    def _restart_desktop(self, page) -> None:
        log.info("Clicking '%s' → Restart...", self.config.desktop_name)
        page.get_by_text(self.config.desktop_name, exact=False).first.click()
        page.wait_for_selector(".appDetails-actions-header", timeout=5_000)
        page.locator(".appDetails-action-restart").click()

        log.info("Confirming restart dialog...")
        page.get_by_role("button", name="Restart").click()

        log.info("Waiting %ds for desktop to restart...", self.config.restart_wait)
        time.sleep(self.config.restart_wait)

        log.info("Refreshing StoreFront page...")
        page.reload(wait_until="networkidle")

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
