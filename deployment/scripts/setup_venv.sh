#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="${1:-$(cd "$DEPLOYMENT_DIR/.." && pwd)}"
VENV_DIR="$REPO_DIR/venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Repo: $REPO_DIR"
echo "Venv: $VENV_DIR"

if [[ ! -f "$REPO_DIR/requirements.txt" ]]; then
  echo "requirements.txt not found in $REPO_DIR" >&2
  exit 1
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r "$REPO_DIR/requirements.txt"

echo
echo "Virtual environment is ready."
echo "Activate with:"
echo "  source \"$VENV_DIR/bin/activate\""
