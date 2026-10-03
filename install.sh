#!/usr/bin/env bash
# One-command setup for macOS / Linux:  ./install.sh [--browser]
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "Python 3.11+ is required (found: $("$PY" --version 2>&1)). Install it from python.org and re-run."; exit 1; }
"$PY" -m venv .venv
. .venv/bin/activate
python -m pip install --quiet --upgrade pip
if [ "${1:-}" = "--browser" ]; then
  python -m pip install --quiet -e ".[browser]"
  python -m playwright install chromium
else
  python -m pip install --quiet -e .
fi
python -m unittest discover -s tests
for f in data/inbox/*.json; do python -m jobagent import "$f" || true; done
echo
python -m jobagent doctor || true
cat <<MSG

Installed. Each time you open a terminal:
  source .venv/bin/activate
  jobagent list
Full command list: jobagent --help   (or see README.md)
MSG
