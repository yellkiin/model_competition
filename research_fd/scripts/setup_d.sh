#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
"$PYTHON" -m venv "$ROOT/research_fd/.venv"
"$ROOT/research_fd/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/research_fd/.venv/bin/python" -m pip install -r "$ROOT/research_fd/requirements_d.txt"
if [[ "${1:-}" == "--full" ]]; then
 "$ROOT/research_fd/.venv/bin/python" -m pip install -r "$ROOT/research_fd/requirements_d_optional.txt"
fi
printf 'Activate: source "%s/research_fd/.venv/bin/activate"\n' "$ROOT"
