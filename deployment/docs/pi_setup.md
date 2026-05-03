# Pi Setup Walkthrough

This is the full rebuild process for a fresh Raspberry Pi.

## 1. Base OS

Flash Raspberry Pi OS, boot the Pi, and get terminal access.

Recommended packages:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

Optional but useful:

```bash
sudo apt install -y i2c-tools v4l-utils
```

## 2. Clone The Repo

Example location:

```bash
mkdir -p /home/connect4/Desktop
cd /home/connect4/Desktop
git clone <YOUR_REPO_URL> Codenect4
cd Codenect4
```

If you are using a non-default branch:

```bash
git fetch origin
git switch <BRANCH_NAME>
```

## 3. Build The Python Environment

From the repo root:

```bash
bash deployment/scripts/setup_venv.sh
```

This creates:

- `venv/`
- upgraded `pip`, `setuptools`, `wheel`
- project dependencies from `requirements.txt`

## 4. Verify The Web Server Manually

Before using systemd, make sure the server works directly:

```bash
source venv/bin/activate
python web_control_server.py
```

If it starts successfully, stop it with `Ctrl+C`.

## 5. Install The systemd Service

From the repo root:

```bash
bash deployment/scripts/install_service.sh
```

Then start and verify it:

```bash
sudo systemctl start codenect4-web.service
sudo systemctl status codenect4-web.service
```

To make it boot automatically:

```bash
sudo systemctl enable codenect4-web.service
```

## 6. Check The Dashboard

The default health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Show likely URLs:

```bash
bash deployment/scripts/show_urls.sh
```

## One-Command Alternative

If you want the fast path instead of the step-by-step flow:

```bash
cd /home/connect4/Desktop/Codenect4
bash deployment/scripts/bootstrap_pi.sh
```

## 7. Restore Tailscale Funnel

If Tailscale is already installed and logged in:

```bash
bash deployment/scripts/enable_funnel.sh
```

Then inspect:

```bash
tailscale funnel status
```

## 8. Common Service Commands

```bash
sudo systemctl restart codenect4-web.service
sudo systemctl stop codenect4-web.service
sudo systemctl start codenect4-web.service
sudo systemctl status codenect4-web.service
journalctl -u codenect4-web.service -f
```

## 9. If The venv Is Broken

Blow away the environment and rebuild it:

```bash
rm -rf venv
bash deployment/scripts/setup_venv.sh
sudo systemctl restart codenect4-web.service
```

## 10. If The Service Hangs On Restart

Use:

```bash
sudo systemctl kill codenect4-web.service
sudo systemctl start codenect4-web.service
```

The provided service template already includes:

- `TimeoutStopSec=5`
- `KillMode=mixed`

to reduce restart stalls.
