#!/usr/bin/env python3
"""
Citrix ICA auto-downloader using headless Playwright browser automation.

Flow:
  1. Navigate to StoreFront → SSO → PingID → YubiKey tap (one notification sent)
  2. Wait for ICA auto-download; if none, click Desktop → Open
  3. Open ICA with local Citrix Workspace
  4. Poll for an established TCP connection (success)
  5. On failure: restart the desktop, wait, re-download, retry

Required env vars:
    CITRIX_STOREFRONT   Full URL to your Citrix StoreFront
    CITRIX_USER         SSO username
    CITRIX_PASS         SSO password

Optional env vars:
    CITRIX_APP              Desktop display name (default: "My Windows 11 Desktop")
    CITRIX_PINGID_URL       URL pattern to match the PingID redirect (default: "**/pingid/**")
    CITRIX_YUBIKEY_TEXT     Button text on the PingID page for YubiKey (default: "YubiKey")
    OUTPUT_DIR              Where to save session.ica (default: ./output)
    MAX_RETRIES             Max restart attempts, 0 = infinite (default: 0)
    RESTART_WAIT            Seconds to wait after VM restart (default: 120)
    CITRIX_RESTART_FIRST    Set to "true" to restart desktop before first attempt
    CITRIX_HEADLESS         Set to "false" to show the browser window (default: true)
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
STOREFRONT    = os.environ["CITRIX_STOREFRONT"]
USERNAME      = os.environ["CITRIX_USER"]
PASSWORD      = os.environ["CITRIX_PASS"]
DESKTOP_NAME  = os.environ.get("CITRIX_APP", "My Windows 11 Desktop")
PINGID_URL    = os.environ.get("CITRIX_PINGID_URL", "**/pingid/**")
YUBIKEY_TEXT  = os.environ.get("CITRIX_YUBIKEY_TEXT", "YubiKey")
OUTPUT_DIR    = Path(os.environ.get("OUTPUT_DIR", "./output"))
MAX_RETRIES   = int(os.environ.get("MAX_RETRIES", "0"))
RESTART_WAIT  = int(os.environ.get("RESTART_WAIT", "120"))
RESTART_FIRST = os.environ.get("CITRIX_RESTART_FIRST", "false").lower() == "true"
HEADLESS      = os.environ.get("CITRIX_HEADLESS", "true").lower() != "false"

ICA_FILE = OUTPUT_DIR / "session.ica"


# ── macOS helpers ──────────────────────────────────────────────────────────────
def notify(message: str, title: str = "Citrix Login") -> None:
    subprocess.run(
        ["osascript", "-e",
         f'display notification "{message}" with title "{title}" sound name "Glass"'],
        check=False,
    )


def session_connected(timeout: int = 45) -> bool:
    """Return True once lsof shows an ESTABLISHED connection from a Citrix process."""
    log.info("Polling for established Citrix TCP connection (up to %ds)...", timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["lsof", "-i", "-nP"],
            capture_output=True, text=True, check=False,
        )
        if "Citrix" in result.stdout and "ESTABLISHED" in result.stdout:
            return True
        time.sleep(3)
    return False


# ── Browser flow ───────────────────────────────────────────────────────────────
def authenticate(page) -> None:
    """
    Navigate to StoreFront, complete SSO + PingID + YubiKey OTP.

    NOTE: Selectors below are best-effort guesses for common SSO/PingID layouts.
    If auth fails at a step, run with headless=False to inspect the actual page
    and adjust the selector for that step.
    """
    log.info("Navigating to StoreFront...")
    page.goto(STOREFRONT, wait_until="domcontentloaded")

    # ── SSO: username + password ───────────────────────────────────────────────
    log.info("Waiting for SSO login page...")
    # Wait for password field — reliable signal that the SSO form has loaded
    page.wait_for_selector("input[type='password']", timeout=20_000)

    # Fill username — try common selector patterns in order of specificity
    for sel in [
        "input[name='username']",
        "input[id='username']",
        "input[type='email']",
        "input[type='text']",
    ]:
        if page.locator(sel).count() > 0:
            page.locator(sel).first.fill(USERNAME)
            break

    page.locator("input[type='password']").fill(PASSWORD)
    log.info("Clicking Sign On...")
    page.locator("#signOnButton").click()

    # ── PingID: YubiKey OTP ────────────────────────────────────────────────────
    # Adjust the URL pattern below to match your PingID redirect URL
    log.info("Waiting for PingID MFA redirect...")
    page.wait_for_url(PINGID_URL, timeout=30_000)

    # Select YubiKey device then click Sign On to proceed to OTP entry page
    log.info("Selecting YubiKey device...")
    page.get_by_text(YUBIKEY_TEXT, exact=False).first.click()

    log.info("Clicking Sign On to proceed to OTP page...")
    page.locator("#device-submit").click()

    # OTP entry page: focus the input and prompt user to tap
    log.info("Waiting for OTP input field...")
    otp_field = page.wait_for_selector(
        "input[type='text']:visible, input[type='tel']:visible, input[type='password']:visible",
        timeout=15_000,
    )
    otp_field.click()

    notify("Tap your YubiKey now")
    log.info("Waiting for YubiKey OTP (tap your key)...")

    # Yubico OTP is ~44 characters; browser auto-redirects once filled
    page.wait_for_function(
        """() => {
            const fields = document.querySelectorAll('input[type="text"], input[type="tel"], input[type="password"]');
            return [...fields].some(el => el.value.length > 10);
        }""",
        timeout=60_000,
    )

    # ── Wait for redirect back to Citrix StoreFront ────────────────────────────
    log.info("Waiting for StoreFront redirect after auth...")
    storefront_host = STOREFRONT.split("//", 1)[1].split("/")[0]
    page.wait_for_url(f"**{storefront_host}**", timeout=30_000)

    # Dismiss the CitrixEndpointAnalysis.app browser dialog and skip the check
    page.on("dialog", lambda d: d.dismiss())
    try:
        page.get_by_text("Skip Check", exact=False).first.click(timeout=10_000)
        log.info("Dismissed endpoint analysis check.")
    except PlaywrightTimeoutError:
        log.info("No endpoint analysis check appeared — continuing.")

    page.wait_for_load_state("networkidle")
    log.info("Authentication complete.")


def download_ica(page, pending_downloads: list) -> bool:
    """
    Try to get an ICA file from the current StoreFront page.
    Checks for an auto-download first; falls back to clicking Desktop → Open.
    Saves the result to ICA_FILE. Returns True on success.
    """
    # Brief wait for any auto-download that triggers on page load
    page.wait_for_load_state("networkidle")
    time.sleep(5)

    if pending_downloads:
        log.info("Auto-download detected.")
        pending_downloads.pop(0).save_as(ICA_FILE)
        log.info("ICA saved to %s", ICA_FILE)
        return True

    # No auto-download — click the desktop entry to trigger one
    log.info("No auto-download. Clicking '%s' → Open...", DESKTOP_NAME)
    try:
        with page.expect_download(timeout=15_000) as dl_info:
            page.get_by_text(DESKTOP_NAME, exact=False).first.click()
            page.get_by_text("Open", exact=True).first.click()
        dl_info.value.save_as(ICA_FILE)
        log.info("ICA saved to %s", ICA_FILE)
        return True
    except PlaywrightTimeoutError:
        log.error("ICA download timed out after clicking Open.")
        return False


def restart_desktop(page) -> None:
    """Click Desktop → Restart, confirm the dialog, wait, then refresh the page."""
    log.info("Clicking '%s' → Restart...", DESKTOP_NAME)
    page.get_by_text(DESKTOP_NAME, exact=False).first.click()
    page.get_by_text("Restart", exact=True).first.click()

    # Confirm the in-page restart dialog
    log.info("Confirming restart dialog...")
    page.get_by_role("button", name="Restart").click()

    log.info("Waiting %ds for desktop to restart...", RESTART_WAIT)
    time.sleep(RESTART_WAIT)

    log.info("Refreshing StoreFront page...")
    page.reload(wait_until="networkidle")


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Single listener captures all downloads for the lifetime of this page
        pending_downloads: list = []
        page.on("download", lambda d: pending_downloads.append(d))

        try:
            authenticate(page)

            if RESTART_FIRST:
                log.info("CITRIX_RESTART_FIRST=true — restarting desktop before first attempt...")
                restart_desktop(page)

            attempt = 0
            while True:
                attempt += 1
                if MAX_RETRIES > 0 and attempt > MAX_RETRIES:
                    log.error("Max retries (%d) reached. Giving up.", MAX_RETRIES)
                    notify("Citrix login failed — max retries reached")
                    sys.exit(1)

                log.info(
                    "=== Attempt %d%s ===",
                    attempt,
                    f" of {MAX_RETRIES}" if MAX_RETRIES else "",
                )

                pending_downloads.clear()

                if not download_ica(page, pending_downloads):
                    log.warning("Could not download ICA — restarting desktop and retrying...")
                    restart_desktop(page)
                    continue

                log.info("Opening ICA with Citrix Workspace...")
                subprocess.run(["open", str(ICA_FILE)], check=True)

                if session_connected(timeout=45):
                    log.info("Citrix session established successfully.")
                    notify("Citrix session is ready")
                    sys.exit(0)

                log.warning("Session failed to connect — restarting desktop...")
                restart_desktop(page)

        finally:
            browser.close()


if __name__ == "__main__":
    main()
