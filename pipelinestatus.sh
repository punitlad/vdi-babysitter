#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

format_run() {
    local label="$1"
    local data="$2"

    if [ "$data" = "null" ] || [ -z "$data" ]; then
        printf "${BOLD}%-16s${RESET}  ${DIM}no runs found${RESET}\n" "$label"
        return
    fi

    local conclusion name url started_at updated_at
    conclusion=$(echo "$data" | jq -r '.conclusion // "in_progress"')
    name=$(echo "$data" | jq -r '.name')
    url=$(echo "$data" | jq -r '.url')
    started_at=$(echo "$data" | jq -r '.startedAt')
    updated_at=$(echo "$data" | jq -r '.updatedAt')

    local start_ts end_ts diff
    start_ts=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$started_at" +%s 2>/dev/null)
    end_ts=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$updated_at" +%s 2>/dev/null)
    diff=$((end_ts - start_ts))
    local duration
    if [ "$diff" -lt 60 ]; then
        duration="${diff}s"
    else
        duration="$((diff / 60))m $((diff % 60))s"
    fi

    local icon color
    case "$conclusion" in
        success)   icon="✓"; color="$GREEN"  ;;
        failure)   icon="✗"; color="$RED"    ;;
        *)         icon="⟳"; color="$YELLOW" ;;
    esac

    local short_name="$name"
    if [ "${#name}" -gt 55 ]; then
        short_name="${name:0:52}..."
    fi

    printf "${BOLD}%-16s${RESET}  ${color}${icon} %-11s${RESET}  %-55s  %-6s  ${DIM}%s${RESET}\n" \
        "$label" "$conclusion" "$short_name" "$duration" "$url"
}

CI=$(gh run list --json name,startedAt,updatedAt,conclusion,url \
    --workflow ci.yml --limit 1 | jq '.[0]')
DEV=$(gh run list --json name,startedAt,updatedAt,conclusion,url \
    --workflow release.yml --event workflow_run --limit 1 | jq '.[0]')
STABLE=$(gh run list --json name,startedAt,updatedAt,conclusion,url \
    --workflow release.yml --event push --limit 1 | jq '.[0]')

echo ""
format_run "CI" "$CI"
format_run "Release (dev)" "$DEV"
format_run "Release (stable)" "$STABLE"
echo ""
