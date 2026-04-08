# vdi-babysitter

Because your VDI can't be trusted to just work on its own.

This tool automates the painful morning ritual of logging into a Citrix VDI — navigating the web portal, surviving SSO and PingID MFA, downloading the ICA file, and dealing with the 50–75% chance that the session fails to connect and needs a full desktop restart before it'll cooperate.

---

## What it does

Every morning, instead of you doing this manually:

1. Open Citrix web portal
2. Log in via SSO (username + password)
3. Get redirected to PingID, select YubiKey, tap key
4. Dismiss the endpoint analysis check
5. Hope the ICA file downloads and the session connects
6. If it doesn't: click Restart, wait 2 minutes, refresh, try again
7. Repeat until it works

...this script does it for you, headlessly, in the background, without touching your active desktop.

---

## How it works

`fetch_ica.py` drives a headless Chromium browser via [Playwright](https://playwright.dev/python/) to automate the full login flow:

1. **SSO** — fills username and password, clicks Sign On
2. **PingID** — selects the YubiKey device, clicks through to OTP entry, injects the OTP value
3. **Endpoint analysis** — dismisses the CitrixEndpointAnalysis native dialog and clicks Skip Check
4. **ICA download** — waits for the auto-download; if it doesn't come, opens the desktop action panel and clicks Open
5. **Greyed-out detection** — if the Open button isn't available yet, reloads and retries up to 5 times
6. **Session check** — opens the ICA with Citrix Workspace and polls for an established TCP connection
7. **Retry loop** — on failure, clicks Restart on the desktop, waits for it to come back up, downloads a fresh ICA, and tries again

The browser runs fully headless — no window appears on your screen. The only thing that shows up is the Citrix Workspace session when it successfully connects.

---

## Requirements

- macOS (uses `osascript`, `lsof`, `open`)
- Python 3.12+ with a `.venv` virtualenv
- [Playwright](https://playwright.dev/python/) + Chromium
- Citrix Workspace installed locally

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```

---

## Configuration

All configuration is via environment variables. Create a `.envrc` (with [direnv](https://direnv.net/)) or export them manually.

| Variable | Required | Default | Description |
|---|---|---|---|
| `CITRIX_STOREFRONT` | Yes | — | Full URL to your Citrix StoreFront |
| `CITRIX_USER` | Yes | — | SSO username |
| `CITRIX_PASS` | Yes | — | SSO password |
| `CITRIX_OTP` | Yes* | — | Static OTP value (skips interactive popup if set) |
| `CITRIX_APP` | No | `My Windows 11 Desktop` | Desktop display name in StoreFront |
| `CITRIX_PINGID_URL` | No | `**/pingid/**` | URL glob pattern to match the PingID redirect |
| `CITRIX_YUBIKEY_TEXT` | No | `YubiKey` | Button text for YubiKey on the PingID device selection page |
| `OUTPUT_DIR` | No | `./output` | Where to save `session.ica` |
| `MAX_RETRIES` | No | `0` (infinite) | Max desktop restart attempts before giving up |
| `RESTART_WAIT` | No | `120` | Seconds to wait after triggering a desktop restart |
| `CITRIX_RESTART_FIRST` | No | `false` | Restart the desktop before the first attempt |
| `CITRIX_HEADLESS` | No | `true` | Set to `false` to show the browser (useful for debugging) |

---

## Usage

```bash
source .envrc
.venv/bin/python fetch_ica.py
```

### Debugging

To see exactly what the browser is doing at each step:

```bash
CITRIX_HEADLESS=false .venv/bin/python fetch_ica.py
```

---

## Scheduling (coming soon)

`launchd` plist to run this automatically every morning before you're even at your desk.

---

## Built by

This tool was built in conjunction with [BMad](https://github.com/bmadcode/bmad-method) and [Claude](https://claude.ai/claude-code) — the brainstorming, architecture decisions, and implementation were all done collaboratively through an AI-assisted development session.

The original approach (Docker + `storebrowse` CLI) was abandoned after constraint mapping revealed that headless Playwright on the host was simpler, more reliable, and didn't have the USB passthrough problems that Docker on macOS introduces.
