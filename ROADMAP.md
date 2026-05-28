# Roadmap

## v1 — Complete

| Feature | Theme | Status | Detail |
|---|---|---|---|
| Headless Playwright browser automation | Core Automation | Complete | No Docker required |
| Full SSO → PingID → YubiKey OTP auth flow | Core Automation | Complete | |
| `--otp` static OTP injection | Core Automation | Complete | |
| `--otp-cmd` shell-command credential helper | Core Automation | Complete | |
| ICA download via network-event-driven flow | Core Automation | Complete | Not DOM polling |
| Citrix Workspace launch via `open` + TCP verification | Core Automation | Complete | |
| Network-event-driven `_download_ica` — Scenario 1 | Reliability | Complete | Auto-download on page load |
| Network-event-driven `_download_ica` — Scenario 2 | Reliability | Complete | Open button → `GetLaunchStatus` polling → download |
| Network-event-driven `_download_ica` — Scenario 3 | Reliability | Complete | `UnavailableDesktop` failure → retry Open → download |
| `_restart_desktop` waits for `PowerOff` response | Reliability | Complete | No sleep |
| `--restart-first` flag | Reliability | Complete | Proactively restarts VM before first attempt |
| `--max-retries` and `--timeout` | Reliability | Complete | Retry and wall-clock bounds |
| `vdi-babysitter citrix connect` | CLI | Complete | Full flag map |
| `vdi-babysitter citrix disconnect` | CLI | Complete | |
| `vdi-babysitter citrix status` | CLI | Complete | `--watch` and `--interval` |
| `vdi-babysitter configure` | CLI | Complete | YAML config management |
| `--output text\|json` | CLI | Complete | Structured output on stdout, logs on stderr |
| `--log-level info\|debug\|quiet` | CLI | Complete | Defaults to `quiet` when `--output json` |
| Human-readable errors by default | CLI | Complete | Full stack traces with `--log-level debug` |
| No args → help text | CLI | Complete | |
| YAML profile system (`~/.vdi-babysitter/config.yaml`) | Config | Complete | |
| Flag → env var → config file precedence | Config | Complete | |
| OTP never stored in config or env var | Config | Complete | |

---

## v2 — Planned

| Feature | Theme | Status | Detail |
|---|---|---|---|
| `VDI_BABYSITTER_DEBUG=1` env var activation | Debug Mode | Complete | Hidden from main CLI help; hard fail if set without `debug.yaml`. See [brainstorming](./_bmad-output/brainstorming/brainstorming-session-2026-05-15-1000.md) |
| `debug.yaml` flat config | Debug Mode | Complete | `playwright_trace`, `playwright_slow_mo`, `capture_screenshots`, `capture_html`, `keep_runs`. See [brainstorming](./_bmad-output/brainstorming/brainstorming-session-2026-05-15-1000.md) |
| TL;DR verdict line | Debug Mode | Complete | First line of debug output: `FAILED at step X after Y retries in Z seconds` |
| Run statistics artifact | Debug Mode | Complete | Timestamp, duration, retry count, vdi-babysitter version, Python version, OS |
| Orchestration flow artifact | Debug Mode | Complete | Chronological breadcrumb trail of every significant action leading to failure |
| Compiled failure block artifact | Debug Mode | Complete | Step name + exception + page URL in one block |
| Playwright `--trace` output | Debug Mode | Complete | Enabled by default when debug mode is active (`playwright_trace: true`) |
| `keep_runs` retention policy | Debug Mode | Complete | Auto-purge old debug output directories; user-configurable in `debug.yaml` |
| `capture_screenshots: true` flag | Debug Mode | Complete | Browser screenshot at failure point; privacy surface — off by default |
| `capture_html: true` flag | Debug Mode | Complete | Browser DOM at failure point; privacy surface — off by default |
| Failure nudge message | Debug Mode | Complete | On failure without debug mode, tip user toward `VDI_BABYSITTER_DEBUG`; only on failures debug mode can help with |
| Local variable capture at failure frames | Debug Mode | | Sentry-style: variable state at each frame of the traceback |
| Low-level Playwright commands in failure block | Debug Mode | | Adds Playwright-level actions to the compiled failure block |
| Post-failure re-run prompt | Debug Mode | | After failure, prompt user to re-run with debug enabled |
| Run manifest artifact | Debug Mode | | Dedicated structured artifact combining run statistics + orchestration flow |
| `vdi-babysitter use <profile>` | CLI | | Persist active profile across invocations |
| `citrix status` health report | CLI | | Last-connect time and reconnect count |
| `citrix connect --keep-alive` | CLI | | Watch mode after connect |
| Shell completions | CLI | | bash, zsh, fish |
| `configure` wizard + `set key value` | CLI | | Imperative config subcommand |
| `vdi-babysitter install` (launchd plist) | Scheduling | | Installs scheduled startup agent |
| YubiKey presence check at startup | Scheduling | | Retry with notification if key not found |
| `--log-level quiet` default under launchd | Scheduling | | |
| Run status persistence | Observability | | Save outcome (success, failure, reason) to structured log after each invocation |
| Post-launch session monitoring | Observability | | Confirm session actually came up after ICA download and Citrix Workspace startup |
| `PowerOff` failure handling | Reliability | | Pending Citrix API research on failure response shapes |
| Scenario 4 edge cases | Reliability | | Post-restart `GetLaunchStatus` with `pollTimeout: 30` |

---

## v3+ — Future

| Feature | Theme | Status | Detail |
|---|---|---|---|
| Single self-contained HTML report | Debug Mode | | TL;DR, orchestration flow, failure block, Playwright trace in one browser-viewable file |
| `--dry-run` mode | Debug Mode | | Show what orchestration would do without executing |
| Extras/hook system | Debug Mode | | Any orchestration step can attach arbitrary data to the debug bundle |
| Failure fingerprint/grouping | Debug Mode | | Hash failure signatures to identify when multiple users hit the same bug |
| Backward tracing from failure | Debug Mode | | Trace causality backward from failure point rather than forward from start |
| Library interface | Debug Mode | | Expose debug artifacts as a reusable library for regression testing and external tooling |
| `--init-debug` config generator | Debug Mode | | Generate a commented `debug.yaml` template for first-time setup |
| `vdi-babysitter aws connect` | Providers | | AWS Workspaces provider |
| Linux platform support | Providers | | |
| Default provider shorthand | Providers | | Skip `citrix` subcommand when only one provider configured |
| `launchd` agent control plane | Platform | | `start`, `stop`, `status` |
| macOS desktop app | Platform | | Native menu bar or windowed app; manage profiles, trigger connects, monitor session status |
