#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p logs
if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
fi
mdq run >> logs/cron.log 2>&1
status=$?
exit "$status"
