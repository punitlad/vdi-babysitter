#!/usr/bin/env python3
"""
Smoke test: validates vdi-babysitter help output against the binary on PATH.
No credentials or live environment required.
"""

import shutil
import subprocess
import sys


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAIL: `{' '.join(cmd)}` exited {result.returncode}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def assert_contains(output: str, *terms: str, cmd: str) -> None:
    for term in terms:
        if term not in output:
            print(f"FAIL: `{cmd}` output missing {term!r}", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    if not shutil.which("vdi-babysitter"):
        print("ERROR: vdi-babysitter not found on PATH", file=sys.stderr)
        sys.exit(1)

    # No args → error message, non-zero exit
    r = subprocess.run(["vdi-babysitter"], capture_output=True, text=True)
    if r.returncode == 0:
        print("FAIL: `vdi-babysitter` (no args) expected non-zero exit", file=sys.stderr)
        sys.exit(1)
    combined = r.stdout + r.stderr
    if "Error: command argument required." not in combined:
        print("FAIL: `vdi-babysitter` (no args) missing expected error message", file=sys.stderr)
        sys.exit(1)
    if not all(t in combined for t in ("citrix", "configure", "use")):
        print("FAIL: `vdi-babysitter` (no args) missing help content", file=sys.stderr)
        sys.exit(1)

    # Top-level --help
    r = run(["vdi-babysitter", "--help"])
    assert_contains(r.stdout + r.stderr, "citrix", "configure", "use", cmd="vdi-babysitter --help")

    # citrix connect --help: key flags present
    r = run(["vdi-babysitter", "citrix", "connect", "--help"])
    combined = r.stdout + r.stderr
    assert_contains(
        combined,
        "--storefront-url",
        "--otp",
        "--otp-cmd",
        "--download-only",
        "--max-retries",
        "--restart-first",
        "--output",
        "--log-level",
        cmd="vdi-babysitter citrix connect --help",
    )

    # citrix disconnect --help
    r = run(["vdi-babysitter", "citrix", "disconnect", "--help"])
    assert_contains(r.stdout + r.stderr, "--output", "--log-level", cmd="vdi-babysitter citrix disconnect --help")

    # citrix status --help
    r = run(["vdi-babysitter", "citrix", "status", "--help"])
    assert_contains(r.stdout + r.stderr, "--watch", "--interval", cmd="vdi-babysitter citrix status --help")

    print("PASS: all smoke tests passed")


if __name__ == "__main__":
    main()
