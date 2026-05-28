"""Debug mode activation, config loading, and session artifact management."""

import json
import os
import platform
import shutil
import sys
import traceback as _tb
from dataclasses import dataclass, field
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Optional

import yaml

from vdi_babysitter.config import CONFIG_DIR

DEBUG_CONFIG_PATH = CONFIG_DIR / "debug.yaml"

VALID_DEBUG_KEYS = {
    "playwright_trace",
    "playwright_slow_mo",
    "capture_screenshots",
    "capture_html",
    "capture_locals",
    "keep_runs",
}


@dataclass
class DebugConfig:
    playwright_trace: bool = True
    playwright_slow_mo: int = 0
    capture_screenshots: bool = False
    capture_html: bool = False
    capture_locals: bool = False
    keep_runs: int = 5


@dataclass
class DebugSession:
    config: DebugConfig
    run_dir: Path
    _start: float = field(default_factory=lambda: __import__("time").time())
    _crumbs: list = field(default_factory=list)
    _pw_actions: list = field(default_factory=list)
    _retries: int = 0
    _step: str = "startup"

    def crumb(self, step: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._crumbs.append(f"[{ts}] {step}")
        self._step = step

    def record_action(self, action: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._pw_actions.append(f"[{ts}] {action}")

    def retry(self) -> None:
        self._retries += 1

    def write(
        self,
        *,
        outcome: str,
        exc: Optional[Exception] = None,
        page_url: Optional[str] = None,
        exc_tb: Optional[str] = None,
    ) -> None:
        import time

        elapsed = time.time() - self._start
        self.run_dir.mkdir(parents=True, exist_ok=True)

        if outcome == "success":
            tldr = f"CONNECTED after {self._retries} retries in {elapsed:.1f}s"
        else:
            tldr = f"FAILED at step '{self._step}' after {self._retries} retries in {elapsed:.1f}s"

        print(tldr, file=sys.stderr)
        print(f"Debug artifacts: {self.run_dir}", file=sys.stderr)

        try:
            pkg_ver = _pkg_version("vdi-babysitter")
        except PackageNotFoundError:
            pkg_ver = "dev"

        stats = "\n".join([
            f"outcome:        {outcome}",
            f"timestamp:      {datetime.now().isoformat(timespec='seconds')}",
            f"duration_s:     {elapsed:.1f}",
            f"retries:        {self._retries}",
            f"vdi-babysitter: {pkg_ver}",
            f"python:         {sys.version.split()[0]}",
            f"platform:       {platform.platform()}",
        ])
        (self.run_dir / "run_statistics.txt").write_text(stats + "\n")

        flow = "\n".join([tldr, ""] + self._crumbs)
        (self.run_dir / "orchestration_flow.txt").write_text(flow + "\n")

        manifest = {
            "outcome": outcome,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "duration_s": round(elapsed, 1),
            "retries": self._retries,
            "tldr": tldr,
            "failed_at_step": self._step if outcome == "failed" else None,
            "vdi_babysitter": pkg_ver,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "orchestration_flow": self._crumbs,
        }
        (self.run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

        if exc is not None:
            block_parts = [
                f"step:  {self._step}",
                f"url:   {page_url or 'unknown'}",
                f"error: {type(exc).__name__}: {exc}",
            ]

            if self.config.capture_locals and exc.__traceback__ is not None:
                te = _tb.TracebackException.from_exception(exc, capture_locals=True)
                block_parts += ["", "traceback (with locals):", "".join(te.format())]
            elif exc_tb:
                block_parts += ["", "traceback:", exc_tb]

            if self._pw_actions:
                block_parts += ["", "playwright actions:"] + self._pw_actions

            (self.run_dir / "failure_block.txt").write_text("\n".join(block_parts) + "\n")

        if outcome == "failed":
            if self.config.playwright_trace:
                print(
                    f"\nTo view the Playwright trace:\n"
                    f"  playwright show-trace {self.run_dir / 'trace.zip'}",
                    file=sys.stderr,
                )
            hints = []
            if not self.config.capture_screenshots:
                hints.append("  capture_screenshots: true   # browser screenshot at failure")
            if not self.config.capture_html:
                hints.append("  capture_html: true          # page DOM at failure")
            if not self.config.capture_locals:
                hints.append("  capture_locals: true        # variable state at each traceback frame")
            if hints:
                print(
                    "\nTo capture more detail on the next run, add to debug.yaml:\n"
                    + "\n".join(hints),
                    file=sys.stderr,
                )


def create_debug_session(config: DebugConfig, base_dir: Optional[Path] = None) -> DebugSession:
    base = base_dir or (CONFIG_DIR / "debug")
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = base / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    return DebugSession(config=config, run_dir=run_dir)


def prune_old_runs(base_dir: Path, keep_runs: int) -> None:
    if not base_dir.exists() or keep_runs <= 0:
        return
    runs = sorted(
        (p for p in base_dir.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
    )
    for old in runs[:-keep_runs]:
        shutil.rmtree(old, ignore_errors=True)


def load_debug_config(debug_config_path: Optional[Path] = None) -> Optional[DebugConfig]:
    """Return a DebugConfig if VDI_BABYSITTER_DEBUG is set, else None.

    Hard fails if the env var is set but debug.yaml is missing or has unknown keys.
    """
    if not os.environ.get("VDI_BABYSITTER_DEBUG"):
        return None

    path = debug_config_path or DEBUG_CONFIG_PATH

    if not path.exists():
        print(
            f"Error: VDI_BABYSITTER_DEBUG is set but {path} was not found.\n"
            f"  Create {path} to enable debug mode.\n"
            f"  See the 'Debug mode' section in README for the required format.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    raw = yaml.safe_load(path.read_text()) or {}

    unknown = set(raw.keys()) - VALID_DEBUG_KEYS
    if unknown:
        print(
            f"Error: Unknown key(s) in {path}: {', '.join(sorted(unknown))}\n"
            f"  Valid keys: {', '.join(sorted(VALID_DEBUG_KEYS))}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return DebugConfig(
        playwright_trace=raw.get("playwright_trace", True),
        playwright_slow_mo=raw.get("playwright_slow_mo", 0),
        capture_screenshots=raw.get("capture_screenshots", False),
        capture_html=raw.get("capture_html", False),
        capture_locals=raw.get("capture_locals", False),
        keep_runs=raw.get("keep_runs", 5),
    )
