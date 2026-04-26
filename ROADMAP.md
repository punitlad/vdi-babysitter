# Roadmap

## v1 — Complete

### Core Automation
- Headless Playwright browser automation (no Docker required)
- Full SSO → PingID → YubiKey OTP auth flow
- `--otp` for static OTP injection; `--otp-cmd` for shell-command credential helper
- ICA download via network-event-driven flow (not DOM polling)
- Citrix Workspace launch via `open` + TCP connection verification

### Reliability
- Network-event-driven `_download_ica` covering three scenarios:
  - Scenario 1: auto-download on page load
  - Scenario 2: Open button click → `GetLaunchStatus` polling → download
  - Scenario 3: `UnavailableDesktop` failure → retry Open → download
- `_restart_desktop` waits for `PowerOff` response instead of sleeping
- `--restart-first` flag to proactively restart VM before first attempt
- `--max-retries` and `--timeout` for retry and wall-clock bounds

### CLI
- `vdi-babysitter citrix connect` with full flag map
- `vdi-babysitter citrix disconnect`
- `vdi-babysitter citrix status` with `--watch` and `--interval`
- `vdi-babysitter configure` for YAML config management
- `--output text|json` — structured output on stdout, logs on stderr
- `--log-level info|debug|quiet` — defaults to `quiet` when `--output json`
- Human-readable errors by default; full stack traces with `--log-level debug`
- No args → help text

### Config
- YAML profile system (`~/.vdi-babysitter/config.yaml`)
- Flag → env var → config file precedence
- OTP never stored in config or env var

---

## v2 — Planned

### CLI
- `vdi-babysitter use <profile>` — persist active profile across invocations
- `vdi-babysitter citrix status` health report with last-connect time and reconnect count
- `vdi-babysitter citrix connect --keep-alive` — watch mode after connect
- Shell completions (bash, zsh, fish)
- `configure` wizard + imperative `set key value` subcommand

### Scheduling
- `vdi-babysitter install` — installs a `launchd` plist for scheduled startup
- YubiKey presence check at startup (retry with notification if key not found)
- `--log-level quiet` as default when running under launchd

### Reliability
- `PowerOff` failure handling — pending Citrix API research on failure response shapes
- Scenario 4 edge cases (post-restart `GetLaunchStatus` with `pollTimeout: 30`)

---

## v3+ — Future

- `vdi-babysitter aws connect` — AWS Workspaces provider
- Linux platform support
- Default provider shorthand (skip `citrix` subcommand when only one provider configured)
- `launchd` agent control plane: `start`, `stop`, `status`
