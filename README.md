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

...`vdi-babysitter` does it for you, headlessly, in the background, without touching your active desktop.

---

## How it works

`vdi-babysitter` drives a headless Chromium browser via [Playwright](https://playwright.dev/python/) to automate the full login flow:

1. **SSO** — fills username and password, clicks Sign On
2. **PingID** — selects the OTP device, clicks through to OTP entry, injects the OTP value
3. **Endpoint analysis** — dismisses the CitrixEndpointAnalysis native dialog and clicks Skip Check
4. **ICA download** — waits for the auto-download; if it doesn't come, opens the desktop action panel and clicks Open
5. **Greyed-out detection** — if the Open button isn't available yet, reloads and retries up to 5 times
6. **Session check** — opens the ICA with Citrix Workspace and polls for an established TCP connection
7. **Retry loop** — on failure, clicks Restart on the desktop, waits for it to come back up, downloads a fresh ICA, and tries again

---

## Requirements

- macOS (uses `osascript`, `lsof`, `open`)
- Python 3.12+
- [Playwright](https://playwright.dev/python/) + Chromium
- Citrix Workspace installed locally

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium
```

---

## Installation

```bash
pip install -e .
```

This installs the `vdi-babysitter` command into your environment.

---

## Usage

### Connect

```bash
vdi-babysitter citrix connect \
  --storefront-url https://your-citrix-storefront.com \
  --username myuser \
  --password mypass \
  --otp <yubikey-tap-value>
```

Or with a shell command to generate the OTP (e.g. via `ykman`):

```bash
vdi-babysitter citrix connect \
  --storefront-url https://your-citrix-storefront.com \
  --username myuser \
  --password mypass \
  --otp-cmd "ykman oath accounts code pingid"
```

### Other commands

```bash
# Check if the session is connected
vdi-babysitter citrix status

# Watch for connection drops (continuous polling)
vdi-babysitter citrix status --watch

# Disconnect the active session
vdi-babysitter citrix disconnect
```

---

## Configuration

Flags take precedence over environment variables, which take precedence over the config file. OTP is the exception — it must always be passed explicitly via `--otp` or `--otp-cmd` and is never read from config or environment.

### Config file

Stored at `~/.vdi-babysitter/config.yaml`. Edit it directly or use the configure commands.

```yaml
profiles:
  default:
    storefront_url: https://your-citrix-storefront.com
    username: myuser
    password: mypass
    desktop_name: My Windows 11 Desktop
    pingid_otp_text: YubiKey 1
```

A project-local `.vdi-babysitter.yaml` in the current directory takes precedence over the global config.

### Profiles

```bash
# Create or edit a profile interactively
vdi-babysitter configure --profile work

# Set a single key
vdi-babysitter configure set storefront_url https://work.storefront.com --profile work

# View a profile
vdi-babysitter configure show --profile work

# List all profiles
vdi-babysitter configure list-profiles

# Switch active profile
vdi-babysitter use work
```

Once a profile is configured, you only need to provide the OTP:

```bash
vdi-babysitter citrix connect --otp <yubikey-value>
```

### Flag reference

| Flag | Env var | Default | Description |
|---|---|---|---|
| `--storefront-url` | `CITRIX_STOREFRONT` | — | Full URL to your Citrix StoreFront |
| `--username` | `CITRIX_USER` | — | SSO username |
| `--password` | `CITRIX_PASS` | — | SSO password |
| `--otp` | — | — | OTP value (mutually exclusive with `--otp-cmd`) |
| `--otp-cmd` | — | — | Shell command whose stdout is the OTP |
| `--desktop-name` | `CITRIX_APP` | `My Windows 11 Desktop` | Desktop display name in StoreFront |
| `--pingid-url` | `CITRIX_PINGID_URL` | `**/pingid/**` | URL glob pattern to match PingID redirect |
| `--pingid-otp-text` | `CITRIX_YUBIKEY_TEXT` | `YubiKey` | Button text for OTP method on PingID page |
| `--output-dir` | — | `~/.vdi-babysitter/output` | Where to save `session.ica` |
| `--max-retries` | `MAX_RETRIES` | `0` (infinite) | Max desktop restart attempts |
| `--restart-wait` | `RESTART_WAIT` | `120` | Seconds to wait after desktop restart |
| `--timeout` | — | — | Max wall-clock seconds for the entire connect operation |
| `--restart-first` | `CITRIX_RESTART_FIRST` | `false` | Restart desktop before first attempt |
| `--no-headless` | — | — | Show the browser window |
| `--download-only` | `CITRIX_DOWNLOAD_ONLY` | `false` | Exit after saving ICA, skip Workspace launch |
| `--output` | — | `text` | Output format: `text`, `json` |
| `--verbose` | — | — | Show INFO-level progress logs |
| `--debug` | — | — | Show DEBUG-level logs (implies full stack traces on error) |
| `--profile` | `VDI_BABYSITTER_PROFILE` | `default` | Config profile to use |

---

## Testing

### E2E test

Requires a live Citrix environment and a valid OTP:

```bash
python test_e2e.py
```

If `CITRIX_OTP` is not set in `.envrc`, a native macOS dialog will appear — tap your YubiKey when prompted.

### Unit tests

```bash
.venv/bin/pytest --cov=vdi_babysitter --cov-fail-under=90 --cov-report=term-missing
```

---

## Built by

This tool was built in conjunction with [BMad](https://github.com/bmadcode/bmad-method) and [Claude](https://claude.ai/claude-code) — the brainstorming, architecture decisions, and implementation were all done collaboratively through an AI-assisted development session.

The original approach (Docker + `storebrowse` CLI) was abandoned after constraint mapping revealed that headless Playwright on the host was simpler, more reliable, and didn't have the USB passthrough problems that Docker on macOS introduces.
