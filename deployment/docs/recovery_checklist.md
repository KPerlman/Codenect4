# Recovery Checklist

Use this when the Pi SD card or environment has to be rebuilt fast.

## Quick Recovery

1. Flash Raspberry Pi OS.
2. Install base tools:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip i2c-tools v4l-utils
```

3. Clone the repo:

```bash
mkdir -p /home/connect4/Desktop
cd /home/connect4/Desktop
git clone <YOUR_REPO_URL> Codenect4
cd Codenect4
```

4. Configure Pi interfaces and reboot:

```bash
sudo bash deployment/scripts/configure_pi_interfaces.sh
sudo reboot
```

5. Reconnect, return to the repo, then run the bootstrap:

```bash
bash deployment/scripts/bootstrap_pi.sh
```

6. If you want to run the steps manually instead of the bootstrap script:

```bash
bash deployment/scripts/configure_pi_interfaces.sh
bash deployment/scripts/setup_venv.sh
bash deployment/scripts/install_service.sh
sudo systemctl start codenect4-web.service
```

7. Verify health:

```bash
curl http://127.0.0.1:8000/health
```

8. Restore Funnel if needed:

```bash
bash deployment/scripts/enable_funnel.sh
```

9. Verify access URLs:

```bash
bash deployment/scripts/show_urls.sh
```

## Sanity Checks

- `sudo systemctl status codenect4-web.service`
- `journalctl -u codenect4-web.service -f`
- `tailscale funnel status`
- `ls /dev/video*`
- `ls /dev/i2c*`
- `fuser /dev/serial0`
- `i2cdetect -y 1`

## High-Risk Things To Recheck

- USB webcam still appears as `/dev/video0`
- I2C bus 1 exists and the PCA9685 appears at `0x40`
- `cmdline.txt` no longer contains `console=serial0,115200`
- `/dev/serial0` is not owned by `serial-getty`
- stepper controller still answers on `/dev/serial0`
- the repo is on the expected branch
- the Funnel URL is the one you expect
