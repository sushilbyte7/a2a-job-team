#!/usr/bin/env bash
# Start all four A2A Job Team servers in the background (macOS/Linux).
# Run from the repo root:  bash demo/start-all.sh
# Stop them with:          bash demo/stop-all.sh
# Requires: .venv with requirements installed, .env with GEMINI_API_KEY
# (or SCRIBE_DRY_RUN=1 to run Scribe without a key).
set -e
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "No .venv found. Run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

mkdir -p /tmp/a2a-logs
.venv/bin/python -m scout.server       > /tmp/a2a-logs/scout.log 2>&1 &
.venv/bin/python -m scribe.server      > /tmp/a2a-logs/scribe.log 2>&1 &
.venv/bin/python -m coordinator.server > /tmp/a2a-logs/coordinator.log 2>&1 &
(cd ui && npm run dev)                 > /tmp/a2a-logs/ui.log 2>&1 &

echo "Started: Scout :10001, Scribe :10002, Coordinator :8000, UI :5173"
echo "Logs in /tmp/a2a-logs/. Open http://127.0.0.1:5173"
echo "Stop with: bash demo/stop-all.sh"
