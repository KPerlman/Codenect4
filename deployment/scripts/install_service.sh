#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="${1:-$(cd "$DEPLOYMENT_DIR/.." && pwd)}"
SERVICE_USER="${SERVICE_USER:-root}"
SERVICE_NAME="${SERVICE_NAME:-codenect4-web.service}"
SERVICE_TEMPLATE="$DEPLOYMENT_DIR/systemd/codenect4-web.service.template"
SERVICE_DEST="/etc/systemd/system/$SERVICE_NAME"

if [[ ! -f "$SERVICE_TEMPLATE" ]]; then
  echo "Service template not found: $SERVICE_TEMPLATE" >&2
  exit 1
fi

if [[ ! -f "$REPO_DIR/web_control_server.py" ]]; then
  echo "web_control_server.py not found in $REPO_DIR" >&2
  exit 1
fi

if [[ ! -x "$REPO_DIR/venv/bin/python" ]]; then
  echo "Missing venv Python at $REPO_DIR/venv/bin/python" >&2
  echo "Run deployment/scripts/setup_venv.sh first." >&2
  exit 1
fi

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

sed \
  -e "s#__SERVICE_USER__#$SERVICE_USER#g" \
  -e "s#__REPO_DIR__#$REPO_DIR#g" \
  "$SERVICE_TEMPLATE" > "$TMP_FILE"

sudo install -m 644 "$TMP_FILE" "$SERVICE_DEST"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo
echo "Installed $SERVICE_NAME"
echo "Start it with:"
echo "  sudo systemctl start $SERVICE_NAME"
echo
echo "Check status with:"
echo "  sudo systemctl status $SERVICE_NAME"
