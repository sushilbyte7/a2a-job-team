#!/usr/bin/env bash
# Stop the servers started by demo/start-all.sh.
pkill -f "python -m scout.server" || true
pkill -f "python -m scribe.server" || true
pkill -f "python -m coordinator.server" || true
pkill -f "vite" || true
echo "Stopped."
