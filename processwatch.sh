#!/bin/bash

WATCH_TERMS="citrix|selfservice|authmanager|wfica|receiver|webhelper"
LOGFILE="citrix_monitor_$(date '+%Y%m%d_%H%M%S').log"
INTERVAL=2

echo "📝 Logging to: $LOGFILE"
echo "🛑 Ctrl+C to stop"

while true; do
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

  {
    echo "════════════════════════════════════════"
    echo "TIMESTAMP: $TIMESTAMP"
    echo "════════════════════════════════════════"

    echo "── PS AUX ──────────────────────────────"
    ps aux | grep -iE "$WATCH_TERMS" | grep -v grep || echo "(none)"

    echo "── LSOF ────────────────────────────────"
    lsof -i -nP 2>/dev/null | grep -iE "$WATCH_TERMS" || echo "(none)"

    echo ""
  } >> "$LOGFILE"

  sleep $INTERVAL
done