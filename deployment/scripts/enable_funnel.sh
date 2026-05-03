#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"

sudo tailscale funnel --bg --https=443 "http://127.0.0.1:$PORT"
tailscale funnel status
