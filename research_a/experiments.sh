#!/usr/bin/env bash
# Execute experiment stages explicitly; no background work or implicit phase switch.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-research_a/.venv/bin/python}"
OUT="${OUT_ROOT:-research_a/runs}"
WORKERS="${WORKERS:-2}"
VARIANT="${MAIN_VARIANT:-full}"
mkdir -p "$OUT"
if [[ ! -f "$OUT/cases.json" ]]; then
  "$PY" -m research_a.run prepare --out "$OUT/cases.json"
fi
case "${1:-dev}" in
  dev)
    "$PY" -m research_a.run run --manifest "$OUT/cases.json" --split dev --questions 1 2 3 --cores 2 4 --variants common full no_memory no_cache --seeds 0 1 2 --budget 24 --workers "$WORKERS" --out "$OUT/dev" --resume
    "$PY" -m research_a.report analyze --source "$OUT/dev" --out "$OUT/dev_report"
    ;;
  main)
    "$PY" -m research_a.run run --manifest "$OUT/cases.json" --questions 1 2 3 --cores 1 2 3 4 5 --variants rr "$VARIANT" --seeds 0 --budget 32 --workers "$WORKERS" --out "$OUT/main" --resume
    "$PY" -m research_a.report analyze --source "$OUT/main" --out "$OUT/main_report"
    ;;
  cross)
    "$PY" -m research_a.run cross --source "$OUT/main" --variant "$VARIANT" --cores 1 2 3 4 5 --seeds 0 --out "$OUT/cross" --resume
    "$PY" -m research_a.report cross --source "$OUT/cross" --out "$OUT/cross_report"
    ;;
  granularity)
    "$PY" -m research_a.run granularity --manifest "$OUT/cases.json" --split dev --questions 1 2 3 --cores 2 4 5 --out "$OUT/granularity"
    ;;
  *) printf 'Usage: bash research_a/experiments.sh {dev|main|cross|granularity}\n' >&2; exit 2 ;;
esac
