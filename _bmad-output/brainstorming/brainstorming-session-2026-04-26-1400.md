---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: []
session_topic: 'GitHub Actions CI pipeline + Homebrew distribution for vdi-babysitter'
session_goals: 'Confidence in built CLI via CI; versioned releases; brew install as end state'
selected_approach: 'ai-recommended'
techniques_used: ['Question Storming', 'Morphological Analysis', 'Decision Tree Mapping']
ideas_generated: [8]
context_file: ''
session_active: false
workflow_completed: true
---

# Brainstorming Session Results

**Facilitator:** punitlad
**Date:** 2026-04-26

---

## Session Overview

**Topic:** GitHub Actions CI pipeline + Homebrew distribution for `vdi-babysitter`
**Goals:** Confidence in the built CLI via automated CI; versioned releases via git tags; `brew install vdi-babysitter` as the end state

### Session Setup

Single user session (punitlad). Project is at v1 complete — `vdi-babysitter` CLI is working, tested, and published to `github.com/punitlad/vdi-babysitter`. Goal is to add a CI/CD pipeline that gates every push, automates releases, and publishes to a private Homebrew tap.

---

## Technique Selection

**Approach:** AI-Recommended Techniques

**Recommended Techniques:**
- **Question Storming:** Surface unknowns before designing — Homebrew Python formula type, versioning, tap structure, auth
- **Morphological Analysis:** Map pipeline design axes systematically — trigger × job structure × release mechanism × formula update strategy
- **Decision Tree Mapping:** Convert morphological grid into concrete, implementable workflow files

---

## Question Storming — Decisions Captured

| Decision | Choice | Rationale |
|---|---|---|
| Homebrew distribution | Private tap: `punitlad/homebrew-tap` | Full control, no acceptance process, distributable immediately |
| Formula type | Bundled virtualenv (`virtualenv_install_with_resources`) | Self-contained, isolated from system Python, standard for Python CLIs; Playwright browser step is unavoidable regardless of formula type |
| Versioning | Semantic versioning via git tag (`v0.1.0`, `v0.2.0`) | Simple, standard, directly triggers release pipeline |
| CI trigger | Push to `main` + PR to `main` | Gates all changes |
| Release trigger | `workflow_run` on `ci.yml` success | Release never runs if CI fails; clean separation |
| Dev release naming | `latest-dev` tag (rolling, overwritten) | Separate from version tags; always points to HEAD of main; previous dev builds irrelevant |
| Python versions | 3.12 only | Matches current requirement; broader matrix deferred to v2 |
| Smoke test scope | `vdi-babysitter --help` + `vdi-babysitter citrix connect --help` exit 0 | Live Citrix environment not available in CI |
| Auth for cross-repo commits | PAT with `repo` scope stored as `HOMEBREW_TAP_TOKEN` | Standard GitHub Actions pattern for cross-repo writes |

---

## Morphological Analysis

**Axis A: Job Structure**
- **A2 selected:** `test` job + `release` job. Build artifact happens inline in `release` job. No separate `build` job needed — artifact is not reused across jobs.

**Axis B: Release Mechanism**
- **B2 selected:** `softprops/action-gh-release` — handles asset uploads (sdist, wheel) cleanly; standard for Python projects.

**Axis C: Dev Release Naming**
- **C3 selected:** `latest-dev` tag — separate from version tags, always rolling forward, simpler for Homebrew dev formula to reference.

**Axis D: Homebrew Formula Update Strategy**
- **D3 for stable releases:** `bump-homebrew-formula` action — automates version + SHA256 bump on tag push
- **D2 for dev builds:** Direct commit to `homebrew-tap` — computes SHA256 of new tarball, renders dev formula, commits; action not appropriate for "same version, new SHA256" rolling updates

**Why D3 doesn't work for dev:** `bump-homebrew-formula` assumes a version bump. For rolling dev builds, only the SHA256 changes — not the version string. D2 (4 shell steps) is simpler and fully in control.

---

## Decision Tree Mapping

**[Decision Tree #1]: Workflow file structure**

GitHub Actions best practice: separate files per responsibility. `workflow_run` trigger cleanly gates release on CI success without conditional complexity.

```
.github/workflows/
├── ci.yml          — triggers: push to main + PR to main
│   └── job: test
│       ├── checkout
│       ├── python 3.12, ubuntu-latest
│       ├── pip install -e ".[dev]"
│       ├── pytest --cov=vdi_babysitter --cov-fail-under=90
│       ├── pip install -e .
│       └── smoke: vdi-babysitter --help && vdi-babysitter citrix connect --help
│
└── release.yml     — triggers: workflow_run(ci.yml completed, main branch only)
    ├── job: dev-release (always on push to main)
    │   ├── python -m build → sdist + wheel
    │   ├── upload tarball → latest-dev GitHub Release (overwrite)
    │   └── compute SHA256 → commit vdi-babysitter-dev.rb to homebrew-tap
    │       └── auth: HOMEBREW_TAP_TOKEN secret (PAT, repo scope)
    │
    └── job: stable-release (if: github.ref starts with refs/tags/v*)
        ├── python -m build → sdist + wheel
        ├── softprops/action-gh-release → attach sdist + wheel as assets
        └── bump-homebrew-formula → punitlad/homebrew-tap
            └── updates Formula/vdi-babysitter.rb: version + SHA256
```

**[Decision Tree #2]: Trigger chain**

```
Push to main (no tag)
→ ci.yml: test + smoke
→ release.yml: dev-release job
  → latest-dev GitHub Release updated
  → vdi-babysitter-dev.rb in homebrew-tap updated

Push tag v0.2.0
→ ci.yml: test + smoke
→ release.yml: dev-release + stable-release jobs
  → stable GitHub Release created with sdist + wheel
  → vdi-babysitter.rb in homebrew-tap bumped to v0.2.0
```

**[Decision Tree #3]: Homebrew tap formula structure**

```
punitlad/homebrew-tap/
└── Formula/
    ├── vdi-babysitter.rb       — stable, updated by bump-homebrew-formula on tag
    └── vdi-babysitter-dev.rb   — rolling latest-dev, updated by D2 commit on push
```

User install:
```bash
brew tap punitlad/homebrew-tap
brew install vdi-babysitter        # stable
brew install vdi-babysitter-dev    # latest dev build
```

Both formulas use `virtualenv_install_with_resources` with SHA256-pinned deps. User runs `playwright install chromium` post-install (unavoidable regardless of formula type).

---

## Idea Organization and Prioritization

### Thematic Organization

**Theme 1: CI Workflow (`ci.yml`)**
Test, coverage gate, smoke test. Runs on every push and PR. Simple, no conditionals.

**Theme 2: Release Workflow (`release.yml`)**
`workflow_run` triggered. Dev-release always; stable-release only on `v*` tags. Two jobs, clean separation.

**Theme 3: Homebrew Tap Structure**
Two formulas: stable + dev. Both bundled virtualenv. Private tap under `punitlad/homebrew-tap`.

**Theme 4: Auth + Secrets**
Single PAT (`HOMEBREW_TAP_TOKEN`) with `repo` scope covers both formula update paths.

### Prioritization Results

- **Top Priority:** `ci.yml` — gates all future work; implement first
- **Second:** `release.yml` dev-release job — gets dev formula flowing immediately
- **Third:** Homebrew tap setup (repo + formula stubs + PAT)
- **Fourth:** `release.yml` stable-release job — needed for `v0.1.0` tag

### Action Plan

**Step 1 — Homebrew tap setup:**
1. Create `punitlad/homebrew-tap` repo with `Formula/` directory
2. Write initial `vdi-babysitter.rb` and `vdi-babysitter-dev.rb` formula stubs (bundled virtualenv)
3. Generate PAT with `repo` scope
4. Store PAT as `HOMEBREW_TAP_TOKEN` in `punitlad/vdi-babysitter` repo secrets

**Step 2 — CI workflow:**
1. Create `.github/workflows/ci.yml`
2. Install deps → pytest with 90% coverage gate → install CLI → smoke test

**Step 3 — Release workflow:**
1. Create `.github/workflows/release.yml`
2. Wire `workflow_run` trigger on `ci.yml` completed on `main`
3. Dev-release job: `python -m build` → upload to `latest-dev` → SHA256 → commit `vdi-babysitter-dev.rb`
4. Stable-release job: `python -m build` → `action-gh-release` → `bump-homebrew-formula`

**Step 4 — Validate end-to-end:**
1. Push to main → CI passes + dev release created + `vdi-babysitter-dev.rb` updated
2. Push `v0.1.0` tag → stable release created + `vdi-babysitter.rb` updated
3. `brew tap punitlad/homebrew-tap && brew install vdi-babysitter` on a clean machine

---

## Session Summary and Insights

**Key Achievements:**
- Designed a complete CI/CD + Homebrew distribution pipeline from scratch
- Resolved the Python/Homebrew formula type question — bundled virtualenv is correct; Playwright browser step is the real constraint either way
- Clean separation: two workflow files, `workflow_run` gating, no conditional complexity
- Two-formula tap strategy (stable + dev) gives full control over what users pull

**Breakthrough Moment:**
Why D3 (`bump-homebrew-formula`) doesn't work for dev builds — it assumes a version bump, not a SHA256-only update. This insight prevented a design that would have been broken in practice.

**Key Constraint:**
`playwright install chromium` cannot be automated by the Homebrew formula. This is unavoidable and must be documented in the formula cask description and README.

**Next Debugging / Research:**
- Exact `virtualenv_install_with_resources` syntax for pinning Playwright + Typer + PyYAML with SHA256s
- Whether `bump-homebrew-formula` action requires any specific formula structure to work correctly

### Creative Facilitation Narrative

The session started with a clear end goal (`brew install`) but several non-obvious unknowns in the path. Question Storming surfaced the most important one early: Homebrew's Python formula types. Understanding that `playwright install chromium` is unavoidable regardless of formula type eliminated the "heaviness" concern and made the bundled virtualenv choice obvious. Morphological Analysis then cleanly separated the dev vs. stable release strategies — and the Question Storming insight about D3 not fitting rolling dev builds came directly from understanding the `bump-homebrew-formula` action's assumptions. The result is a pipeline design with no ambiguity in any step.
