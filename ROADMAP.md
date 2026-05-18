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

### Debug Mode
Debug mode is opt-in, explicitly activated, and maintainer-first — it exists to give the author enough signal to make durable implementation fixes. vdi-babysitter does not own the external services it interacts with, so all capture requires explicit user consent.

**Activation**
- `VDI_BABYSITTER_DEBUG=1` env var enables debug mode — intentionally not surfaced in main CLI help
- `debug.yaml` flat config required; hard fail with clear error if env var is set but file is missing
- Consent is the user's act of setting the env var — recorded inside every artifact (CLI invocation, timestamp, flags)

**`debug.yaml` v1 shape (flat list)**
```yaml
playwright_trace: true
playwright_slow_mo: 0      # milliseconds, 0 = disabled
capture_screenshots: false # v2 debug mode addition
capture_html: false        # v2 debug mode addition
keep_runs: 5               # number of debug output directories to retain
```

**Artifacts captured (initial)**
- TL;DR verdict line — first line of output: `FAILED at step X after Y retries in Z seconds`
- Run statistics — timestamp, duration, retry count, inputs (pingid, url), vdi-babysitter version, Python version, OS
- Orchestration flow — chronological breadcrumb trail of every significant action leading to failure
- Compiled failure block — step name + Playwright action that failed + exception + page URL
- Playwright `--trace` output (when `playwright_trace: true`)
- `keep_runs` auto-purge of old debug output directories

**Architecture**
- Wrapper instrumentation over existing flow — not a separate execution path
- `except` blocks check debug flags and act accordingly
- Existing logs already contain orchestration context; debug mode surfaces it more clearly

**Subsequent debug mode additions (still v2)**
- `capture_screenshots: true` — browser screenshot at failure point
- `capture_html: true` — browser DOM at failure point
- Failure nudge message — on failure without `VDI_BABYSITTER_DEBUG`, output a tip pointing toward debug mode (only on failures where debug mode adds signal, not config/missing-file errors)
- Sentry-style local variable capture at each frame of the failure traceback
- Low-level Playwright commands included in compiled failure block
- Post-failure re-run prompt — "that run failed, re-run with debug enabled?"
- Run manifest — dedicated structured artifact combining run statistics + orchestration flow

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

### Observability
- Run status persistence — save outcome (success, failure, reason, etc.) to a structured log or state file after each invocation
- Post-launch session monitoring — after ICA download and Citrix Workspace startup, monitor the active session to confirm it actually came up (not just that the process launched)

### Reliability
- `PowerOff` failure handling — pending Citrix API research on failure response shapes
- Scenario 4 edge cases (post-restart `GetLaunchStatus` with `pollTimeout: 30`)

---

## v3+ — Future

### Debug Mode
- Single self-contained HTML report — TL;DR, orchestration flow, failure block, and Playwright trace in one browser-viewable file
- `--dry-run` mode — show what the orchestration flow would do without executing
- Extras/hook system — any orchestration step can attach arbitrary data to the debug bundle
- Failure fingerprint/grouping — hash failure signatures to identify when multiple users hit the same underlying bug
- Backward tracing from failure — trace causality backward from failure point rather than forward from start
- Library interface — expose debug mode artifacts as a reusable library for regression testing and external tooling
- `--init-debug` — generate a commented `debug.yaml` template for first-time setup

### Providers
- `vdi-babysitter aws connect` — AWS Workspaces provider
- Linux platform support
- Default provider shorthand (skip `citrix` subcommand when only one provider configured)

### Platform
- `launchd` agent control plane: `start`, `stop`, `status`
- macOS desktop app — native menu bar or windowed app wrapping the CLI for users who prefer a GUI; manage profiles, trigger connects, and monitor session status without the terminal
