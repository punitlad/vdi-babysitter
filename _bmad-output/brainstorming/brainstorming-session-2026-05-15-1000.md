---
stepsCompleted: [1, 2, 3, 4]
workflow_completed: true
session_active: false
inputDocuments: []
session_topic: 'Debug/Developer mode for vdi-babysitter CLI'
session_goals: 'Design a mode that exposes CLI internals and captures failure artifacts (screenshots, HTML) so users can share failure context with the author to improve robustness'
selected_approach: 'ai-recommended'
techniques_used: ['Question Storming', 'SCAMPER Method', 'Cross-Pollination']
ideas_generated: ['VDI_BABYSITTER_DEBUG env var', 'debug.yaml flat config', 'explicit opt-in consent model', 'wrapper architecture', 'TL;DR verdict line', 'run statistics with environment', 'orchestration flow as breadcrumbs', 'compiled failure block', 'Playwright trace default', 'slowMo configurable', 'keep_runs retention policy', 'two-section output structure']
context_file: ''
session_continued: true
continuation_date: '2026-05-18'
technique_execution_complete: true
---

# Brainstorming Session Results

**Facilitator:** punitlad
**Date:** 2026-05-15

## Session Overview

**Topic:** Debug/Developer mode for vdi-babysitter CLI
**Goals:** Design a mode that exposes CLI internals and captures failure artifacts (screenshots, HTML) so users can share failure context with the author to improve robustness

### Session Setup

vdi-babysitter orchestrates a flaky system (Citrix VDI). The author cannot be present when failures occur, so debug mode must make failures self-documenting. Users need to capture and share enough context (screenshots, HTML state, Playwright internals, log config) that the author can diagnose and improve the CLI without being there.

## Technique Selection

**Approach:** AI-Recommended Techniques
**Analysis Context:** Feature design for a concrete, known problem — flaky VDI sessions that are hard to debug remotely

**Recommended Techniques:**

- **Question Storming:** Surface all unanswered design questions before generating solutions — defines the real problem space
- **SCAMPER Method:** Systematically explore debug mode through 7 lenses to prevent designing only the obvious version
- **Cross-Pollination:** Steal patterns from adjacent debugging tools (Playwright reporter, Cypress, Sentry, pytest-html)

**AI Rationale:** The problem is concrete and the tool is well-understood, but the *debug experience design* has many implicit assumptions. Question Storming surfaces those first, SCAMPER generates ideas across all dimensions systematically, and Cross-Pollination brings in proven patterns from tools that have already solved adjacent problems.

## Question Storming Results

### Key Design Decisions Locked

**1. Explicit opt-in only**
Debug mode requires the user to consciously pass `--debug`. It is never on by default, never retroactive. The act of invoking `--debug` IS the user's consent to artifact capture. Rationale: vdi-babysitter does not own any of the external services it interacts with (Citrix StoreFront, PingID, etc.) and cannot capture data from them without explicit user permission.

**2. Consent recorded in the artifact**
The debug bundle must self-document that it was produced via explicit invocation — CLI command, timestamp, flags passed. This makes the consent act traceable inside the artifact itself.

**3. Everything stored locally**
No external servers. Artifacts land on the user's own filesystem. The privacy risk is not capture — it is the user's choice to attach artifacts to a public GitHub issue. That moment is the user's responsibility, not vdi-babysitter's.

**4. Failure nudge message**
On failure without `--debug`, vdi-babysitter outputs a tip pointing users toward debug mode. This is the on-ramp from "frustrated user" to "helpful contributor." The nudge should only appear on failures where debug mode would actually add signal — not on config errors or missing files.

**5. Tiered capture model**
- **Tier 1 — always captured in debug mode:** Run statistics, code flow, orchestration flow. Low privacy risk, high diagnostic signal.
- **Tier 2 — explicit flags within debug mode:** HTML state, screenshots. Higher privacy surface (corporate login pages, SSO tokens), require opt-in within opt-in.

**6. Wrapper architecture**
Debug mode is instrumentation layered on top of the existing flow — not a separate execution path. `except` blocks check debug flags and act accordingly. The existing logs already contain orchestration context; debug mode makes that context easier to parse and present.

**7. Primary consumer is the author (maintainer), not the user**
Debug mode exists to give the author enough signal to make durable implementation fixes. Users enabling it are doing the author a favor. The design must make that favor as easy as possible to give.

**8. v1 is iterative**
Implementation priority order: run statistics → code flow → orchestration flow → HTML state → screenshots. Start with what's cheapest to capture and highest in signal.

### v1 Artifact Bundle

| Artifact | Tier | Rationale |
|---|---|---|
| Run statistics (retry count, timestamp, duration, inputs) | 1 | Envelope that makes everything else interpretable |
| Code flow (file, line, call stack at failure) | 1 | Cheapest to capture, highest signal |
| Orchestration flow (which step failed, preceding steps) | 1 | Already in logs, needs better presentation |
| HTML state (browser DOM at failure) | 2 | Privacy surface — corporate page content |
| Screenshots (browser visual at failure) | 2 | Privacy surface — visible credentials/SSO |

### Open Questions Carried Forward

- Input sanitization: should pingid, url be redacted or echoed verbatim in the artifact?
- Bundle format: directory of files, zip, structured JSON, or markdown report?
- Nudge message: context-aware (which step failed) or generic?
- Orchestration flow format: structured artifact vs. parsed/filtered existing logs?

## SCAMPER Results

### Net-New Decisions from SCAMPER

| Decision | Lens | Priority |
|---|---|---|
| `VDI_BABYSITTER_DEBUG` env var activates debug mode | Substitute | v1 |
| `debug.yaml` flat config — hard fail if env var set but file missing | Substitute | v1 |
| Playwright `--trace` enabled by default in debug mode | Adapt | v1 |
| `slowMo` configurable via `debug.yaml` (e.g. `playwright_slow_mo: 500`) | Modify | v1 |
| Sentry-style local variable capture at failure frames | Adapt | v2 |
| `--dry-run` mode — show what orchestration would do without executing | Put to other uses | v3+ |
| Failure nudge message | Eliminate | v2 |
| Run manifest as separate artifact | Eliminate | v2 |
| Tiered capture framing | Eliminated — replaced by incremental feature rollout | — |

### v1 Scope (locked after SCAMPER)

- **Activation:** `VDI_BABYSITTER_DEBUG=1` + `debug.yaml` present (hard fail if either missing)
- **`debug.yaml`:** Flat list of flags — `playwright_trace`, `playwright_slow_mo`, `capture_screenshots`, etc.
- **Artifacts captured:** Run statistics, code flow (file/line/call stack), orchestration flow, Playwright trace
- **Screenshots + HTML:** Later additions, not v1
- **`--init-debug`:** Nice to have, not v1 — explicitness is a feature

### SCAMPER Rejected / Deferred

- Post-failure re-run prompt → v2 (same as nudge message)
- Backward tracing from failure → explore when debug maturity warrants it
- Execution behavior changes (waits/confirmations) → rejected, introduces human steps
- Golden run snapshot / diff baseline → possible future brainstorm
- Every Playwright action logged → v3+
- Run manifest as timeline → v3+, conflicts with existing logging

### Question Storming Facilitation Notes

The most productive thread was the privacy/consent question — it forced a clear answer: vdi-babysitter doesn't own the external services, so it cannot act without explicit user permission. That single insight drove the tiered capture model and the consent-recording requirement. The flakiness/non-determinism question surfaced that retroactive debug mode is unreliable, which confirmed explicit opt-in as the only viable design. The "who is the consumer" question clarified that this is a maintainer tool, not a user support tool — which sets the right scope for v1.

## Cross-Pollination Results

### Patterns Borrowed and Decisions Made

**From Playwright Reporter:**

| Pattern | Decision |
|---|---|
| Single self-contained HTML report | v3+ nice-to-have — plain text/JSON for v1 |
| "What happened" vs "what went wrong" separation | Adopted — two clear sections: orchestration flow + code flow |
| Failures-only filtering | Rejected — keep it simple, no filtering |

**From Cypress:**

| Pattern | Decision |
|---|---|
| Single compiled failure block (step + action + exception + URL) | Adopted for v1 code flow section |
| Timestamped command log | Already in existing logs — surfaced cleanly in orchestration flow |
| Auto-purge of older runs | Adopted — `keep_runs` field in `debug.yaml`, user-configurable |
| Low-level Playwright commands in failure block | v2 |

**From Sentry:**

| Pattern | Decision |
|---|---|
| Breadcrumbs — chronological event trail to failure | Adopted for v1 orchestration flow section |
| Environment capture (versions, OS, platform) | Adopted for v1 run statistics |
| Failure fingerprint/grouping | v3+ |

**From pytest-html:**

| Pattern | Decision |
|---|---|
| TL;DR verdict line before all detail | Adopted for v1 — first line: `FAILED at step X after Y retries in Z seconds` |
| Extras/hook system for arbitrary step attachments | v3+ |
| stdout/stderr capture | Not needed — CLI run by human, terminal handles it |

### Final v1 Artifact Structure (after all three techniques)

```
debug output/
├── [TL;DR verdict line]           # FAILED at step X after Y retries in Z seconds
├── run_statistics                 # timestamp, duration, retry count, inputs, vdi-babysitter version, Python version, OS
├── orchestration_flow             # breadcrumb trail — every significant action timestamped, leading to failure
├── code_flow                      # compiled failure block: step name + Playwright action + exception + page URL
└── playwright_trace               # Playwright --trace output (if playwright_trace: true in debug.yaml)
```

### debug.yaml v1 Shape (flat list)

```yaml
playwright_trace: true
playwright_slow_mo: 0          # milliseconds, 0 = disabled
capture_screenshots: false     # v2
capture_html: false            # v2
keep_runs: 5                   # number of debug output directories to retain
```

### Full Versioned Roadmap

**v1 (now):**
- `VDI_BABYSITTER_DEBUG=1` + `debug.yaml` required, hard fail if either missing
- TL;DR verdict line
- Run statistics (timing, retries, inputs, environment)
- Orchestration flow as breadcrumb trail
- Compiled failure block (step + exception + page URL)
- Playwright trace
- `keep_runs` retention policy

**v2:**
- Failure nudge message on non-debug failures
- Sentry-style local variable capture at failure frames
- Low-level Playwright commands in failure block
- Post-failure re-run prompt
- Run manifest artifact
- Screenshots + HTML capture flags in debug.yaml

**v3+:**
- Single HTML report
- `--dry-run` mode
- Extras/hook system for step-level attachments
- Failure fingerprint/grouping
- Backward tracing from failure
- Library interface for external reuse
- `--init-debug` config generator

## Idea Organization and Prioritization

### Thematic Organization

**Theme 1 — Activation & Consent Model**
_The contract that governs how debug mode gets turned on and why explicitness matters_

- `VDI_BABYSITTER_DEBUG=1` env var — intentionally hidden from main CLI help, keeps primary UX clean
- `debug.yaml` flat config required — hard fail if env var set but file missing, no silent defaults
- Explicitness is the design principle throughout — user must take two deliberate actions to enable debug mode
- Consent is the user's act of setting the env var — recorded inside the artifact (CLI invocation, timestamp, flags)
- vdi-babysitter doesn't own the external services — it cannot capture data without explicit user permission

**Theme 2 — v1 Artifact Structure**
_What actually gets captured and how it's presented_

- TL;DR verdict line — `FAILED at step X after Y retries in Z seconds` — first line, sets context before detail
- Run statistics — timing, retry count, inputs (pingid, url), vdi-babysitter version, Python version, OS
- Orchestration flow — chronological breadcrumb trail of every significant action leading to failure
- Compiled failure block — step name + Playwright action that failed + exception + page URL — one place, all context
- Playwright `--trace` on by default when debug mode is active

**Theme 3 — Configuration & Housekeeping**
_debug.yaml shape and artifact lifecycle_

- Flat list of flags for v1, iterated later
- `playwright_slow_mo` — configurable slowdown for entire debug run (applied globally, not per-step)
- `keep_runs` — auto-purge old debug directories, user controls the number
- Wrapper architecture — instrumentation layered over existing flow, not a separate execution path
- `except` blocks check debug flags and act accordingly

**Theme 4 — Versioned Roadmap**
_Everything named, dated, and deferred intentionally_

- v2: failure nudge message, local variable capture at frames, screenshots/HTML flags, post-failure re-run prompt, run manifest
- v3+: single HTML report, `--dry-run`, extras/hook system, library interface, failure fingerprinting, `--init-debug`

### Prioritization

**Top 3 — Implement First**

1. **Activation model** — env var + debug.yaml + hard fail. Sets the entire design contract. Everything else depends on this.
2. **Compiled failure block** — highest signal-to-effort ratio. One well-formatted artifact that gives the most diagnostic value.
3. **Run statistics with environment** — cheap to add, immediately makes bug reports actionable (version-specific bugs become diagnosable).

**Quick Wins (add alongside top 3):**
- TL;DR verdict line — one line, zero infrastructure
- Playwright trace — just a flag, Playwright already does the work
- `keep_runs` — a few lines to prevent artifact accumulation from day one

**Deliberate Deferrals:**
- Screenshots and HTML — privacy surface, add when there are real users to serve
- Failure nudge message — noise until there's a user base beyond the author

### Action Plan

**Step 1 — Activation infrastructure**
- Add `VDI_BABYSITTER_DEBUG` env var check at startup
- Add `debug.yaml` loader — hard fail with clear error if env var set but file missing
- Define the flat flag schema and document it

**Step 2 — Core artifacts**
- Wire Playwright `--trace` to the debug flag
- Implement run statistics collection (timestamp, duration, retries, inputs, environment)
- Implement compiled failure block in `except` handlers (step name, Playwright action, exception, page URL)
- Implement orchestration flow breadcrumb collection

**Step 3 — Output and housekeeping**
- Write TL;DR verdict line as first output
- Write artifacts to timestamped debug output directory
- Implement `keep_runs` cleanup on each debug run

## Session Summary

**What this session produced:** A complete, implementable v1 spec for debug mode — not just feature ideas but a design philosophy (explicitness, consent, maintainer-first) that resolves every ambiguous decision downstream.

**The insight that drove everything:** vdi-babysitter doesn't own the external services it interacts with. That single constraint resolved the consent model, the activation design, the artifact scope, and the privacy questions — all at once.

**What to build next week:** Activation model first. Everything else is only useful if debug mode can actually be turned on cleanly.
