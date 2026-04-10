# AGENTS.md

## Development

### Testing

There are two levels of testing: unit tests and an e2e test.

#### Unit Tests

Run unit tests with coverage before considering any change complete:

```bash
.venv/bin/pytest --cov=vdi_babysitter --cov-fail-under=90 --cov-report=term-missing
```

Coverage must be at or above **90%** across the `vdi_babysitter` package. If adding new code, add corresponding unit tests. Do not mark a task complete if coverage drops below 90%.

Unit tests live in `tests/` and should not require a live Citrix environment — mock Playwright, subprocess calls, and filesystem interactions as needed.

#### E2E Test

Always run the e2e test before considering a change complete if it touches auth, browser automation, or ICA download logic:

```bash
python test_e2e.py
```

This test requires a live Citrix environment and a valid OTP. If `CITRIX_OTP` is not set in `.envrc`, the native macOS dialog will appear — tap the YubiKey when prompted.

The test validates that `vdi-babysitter citrix connect --download-only` successfully authenticates and downloads `session.ica`. A passing test means auth, PingID, and ICA download all work end-to-end.

Do not mark a task complete if `test_e2e.py` fails.

### Commits

Keep commits small and focused — one logical change per commit. Do not batch unrelated changes together.

Before committing, confirm:
- The change does one thing
- `test_e2e.py` passes (if the change touches auth, browser, or ICA download logic)
- No debug code, commented-out blocks, or temporary files are included

Do not commit `.envrc` — it contains credentials and is gitignored.
