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

## 3. Configure Pi Interfaces

Before hardware testing, configure the Pi so:
- hardware I2C is enabled on bus 1
- sorter software I2C is enabled on bus 3 over GPIO17/27
- `/dev/serial0` is moved onto the stable PL011 UART
- the Linux serial console/getty is removed from `/dev/serial0`

From the repo root:

```bash
sudo bash deployment/scripts/configure_pi_interfaces.sh
sudo reboot
```

After reboot, reconnect and return to the repo root.

## 4. Build The Python Environment

From the repo root:

```bash
bash deployment/scripts/setup_venv.sh
```

This creates:

- `venv/`
- upgraded `pip`, `setuptools`, `wheel`
- project dependencies from `requirements.txt`
- the Pi GPIO backend used by Blinka (`lgpio`)

Important note:
- on Raspberry Pi OS Trixie / Python 3.13, `lgpio` may need the native `lg` library from the official lg archive installed first
- the bootstrap flow now handles that automatically with `deployment/scripts/install_lgpio.sh`

## 5. Verify The Pi Hardware Interfaces

Before moving on, verify the two common failure points are fixed:

```bash
ls -l /dev/i2c*
ls -l /dev/serial0
cat /boot/firmware/cmdline.txt 2>/dev/null || cat /boot/cmdline.txt
fuser /dev/serial0
i2cdetect -y 1
i2cdetect -y 3
```

Expected:
- `/dev/i2c-1` exists
- `/dev/i2c-3` exists
- `/dev/serial0` points to `/dev/ttyAMA0`
- `cmdline.txt` does not contain `console=serial0,115200`
- `fuser /dev/serial0` is empty unless your app is actively using it
- `i2cdetect -y 1` shows the PCA9685 around `0x40`
- `i2cdetect -y 3` shows the sorter TCS34725 around `0x29`

## 6. Verify The Web Server Manually

Before using systemd, make sure the server works directly:

```bash
source venv/bin/activate
python web_control_server.py
```

If it starts successfully, stop it with `Ctrl+C`.

## 7. Install The systemd Service

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

## 8. Check The Dashboard

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

That fast path now:
- configures I2C and UART
- installs the native `lg` library from the official lg archive
- builds the Python venv
- installs the systemd service

## 9. Restore Tailscale Funnel

If Tailscale is already installed and logged in:

```bash
bash deployment/scripts/enable_funnel.sh
```

Then inspect:

```bash
tailscale funnel status
```

## 10. Common Service Commands

```bash
sudo systemctl restart codenect4-web.service
sudo systemctl stop codenect4-web.service
sudo systemctl start codenect4-web.service
sudo systemctl status codenect4-web.service
journalctl -u codenect4-web.service -f
```

## 11. If The venv Is Broken

Blow away the environment and rebuild it:

```bash
rm -rf venv
bash deployment/scripts/setup_venv.sh
sudo systemctl restart codenect4-web.service
```

## 12. If The Service Hangs On Restart

Use:

```bash
sudo systemctl kill codenect4-web.service
sudo systemctl start codenect4-web.service
```

The provided service template already includes:

- `TimeoutStopSec=5`
- `KillMode=mixed`

to reduce restart stalls.
