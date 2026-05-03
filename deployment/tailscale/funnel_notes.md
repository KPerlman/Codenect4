# Tailscale Funnel Notes

The web dashboard can be exposed through Tailscale Funnel as a public HTTPS URL.

Default dashboard URL on the Pi:

```text
http://127.0.0.1:8000
```

## Enable Persistent Funnel

```bash
sudo tailscale funnel --bg --https=443 http://127.0.0.1:8000
```

This usually persists across reboot once configured.

## Check Status

```bash
tailscale funnel status
```

## Reset Funnel

```bash
sudo tailscale funnel reset
```

## Local Health Check

```bash
curl http://127.0.0.1:8000/health
```

## Important Note

Funnel makes the dashboard reachable through a public URL. That is convenient for recovery and mobile access, but it also means anyone with that URL can reach the page.
