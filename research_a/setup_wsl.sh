#!/usr/bin/env bash
# WSL Ubuntu/Debian, Python >=3.10. No CUDA, torch, numpy, or compiler required.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" != "--no-apt" ]]; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv git git-lfs
fi
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python >=3.10 required"'
python3 -m venv "$ROOT/research_a/.venv"
printf '\nEnvironment created. Run in the repository root:\n'
printf '  source research_a/.venv/bin/activate\n'
printf '  git lfs install --local\n'
printf '  git lfs pull --include="题目/A题/**" --exclude=""\n'
printf '  bash research_a/experiments.sh dev\n'
