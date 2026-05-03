#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"

echo "Local health:"
echo "  http://127.0.0.1:$PORT/health"
echo

if command -v hostname >/dev/null 2>&1; then
  echo "LAN addresses:"
  hostname -I 2>/dev/null || true
  echo
fi

if command -v tailscale >/dev/null 2>&1; then
  echo "Tailscale IPs:"
  tailscale ip 2>/dev/null || true
  echo
  echo "Funnel status:"
  tailscale funnel status 2>/dev/null || true
else
  echo "Tailscale CLI not found."
fi
