# Deployment Bundle

This folder is the recovery and rebuild kit for the Raspberry Pi that runs the Connect4 system.

Use it when:
- the SD card is corrupted
- the Pi OS was reflashed
- the `venv` was lost
- the systemd service needs to be recreated
- the Tailscale Funnel setup needs to be restored

## Folder Layout

- `docs/`
  - `pi_setup.md`: full rebuild walkthrough
  - `recovery_checklist.md`: short step-by-step recovery checklist
  - `wiring.md`: hardware assumptions and pin notes
- `scripts/`
  - `bootstrap_pi.sh`: one-command Pi bootstrap for venv + service + first start
  - `setup_venv.sh`: create a fresh virtual environment and install Python deps
  - `install_service.sh`: install the `codenect4-web.service` systemd unit
  - `restart_web.sh`: restart and inspect the web service
  - `show_urls.sh`: show local, Tailscale, and Funnel access info
  - `enable_funnel.sh`: enable persistent public Funnel access for the dashboard
- `systemd/`
  - `codenect4-web.service.template`: template used by `install_service.sh`
- `tailscale/`
  - `funnel_notes.md`: public URL/Funnel notes and commands

## Fast Path

On a fresh Pi, after cloning the repo:

```bash
cd /home/connect4/Desktop/Codenect4
bash deployment/scripts/bootstrap_pi.sh
```

Manual equivalent:

```bash
cd /home/connect4/Desktop/Codenect4
bash deployment/scripts/setup_venv.sh
bash deployment/scripts/install_service.sh
sudo systemctl start codenect4-web.service
bash deployment/scripts/show_urls.sh
```

If you also want the public Funnel URL back:

```bash
bash deployment/scripts/enable_funnel.sh
```

## Assumptions

- repo root on Pi: `/home/connect4/Desktop/Codenect4`
- service name: `codenect4-web.service`
- entrypoint: `web_control_server.py`
- virtualenv location: `venv/`
- web UI port: `8000`
- service user: `root`

These can all be overridden in the scripts if needed.
