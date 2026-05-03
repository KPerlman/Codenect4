#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="${1:-$(cd "$DEPLOYMENT_DIR/.." && pwd)}"
SERVICE_NAME="${SERVICE_NAME:-codenect4-web.service}"

echo "Starting Pi bootstrap for:"
echo "  Repo: $REPO_DIR"
echo

bash "$SCRIPT_DIR/setup_venv.sh" "$REPO_DIR"
echo

bash "$SCRIPT_DIR/install_service.sh" "$REPO_DIR"
echo

sudo systemctl start "$SERVICE_NAME"
echo

echo "Service started. Current status:"
sudo systemctl status "$SERVICE_NAME" --no-pager
echo

echo "Available access info:"
bash "$SCRIPT_DIR/show_urls.sh"
echo

echo "Bootstrap complete."
echo "Optional next step for public access:"
echo "  bash deployment/scripts/enable_funnel.sh"
