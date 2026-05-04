#!/usr/bin/env bash
set -euo pipefail

BOOT_CONFIG="/boot/firmware/config.txt"
CMDLINE_FILE="/boot/firmware/cmdline.txt"

if [[ ! -f "$BOOT_CONFIG" ]]; then
  BOOT_CONFIG="/boot/config.txt"
fi

if [[ ! -f "$CMDLINE_FILE" ]]; then
  CMDLINE_FILE="/boot/cmdline.txt"
fi

if [[ ! -f "$BOOT_CONFIG" ]]; then
  echo "Could not find Raspberry Pi config.txt" >&2
  exit 1
fi

if [[ ! -f "$CMDLINE_FILE" ]]; then
  echo "Could not find Raspberry Pi cmdline.txt" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root or with sudo." >&2
  exit 1
fi

reboot_required=0

echo "Configuring Pi hardware interfaces..."
echo "  config.txt:  $BOOT_CONFIG"
echo "  cmdline.txt: $CMDLINE_FILE"

if grep -Eq '^[[:space:]]*dtparam=i2c_arm=off([[:space:]]*#.*)?$' "$BOOT_CONFIG"; then
  sed -i -E 's/^[[:space:]]*dtparam=i2c_arm=off([[:space:]]*#.*)?$/dtparam=i2c_arm=on/' "$BOOT_CONFIG"
  reboot_required=1
elif ! grep -Eq '^[[:space:]]*dtparam=i2c_arm=on([[:space:]]*#.*)?$' "$BOOT_CONFIG"; then
  printf '\n# Enable hardware I2C for PCA9685/TCS sensors\ndtparam=i2c_arm=on\n' >> "$BOOT_CONFIG"
  reboot_required=1
fi

original_cmdline="$(cat "$CMDLINE_FILE")"
updated_cmdline="$(printf '%s\n' "$original_cmdline" | sed -E 's/(^| )console=(serial0|ttyS0|ttyAMA0),115200//g; s/  +/ /g; s/^ //; s/ $//')"

if [[ "$updated_cmdline" != "$original_cmdline" ]]; then
  printf '%s\n' "$updated_cmdline" > "$CMDLINE_FILE"
  reboot_required=1
fi

for unit in serial-getty@ttyS0.service serial-getty@ttyAMA0.service; do
  systemctl stop "$unit" >/dev/null 2>&1 || true
  systemctl disable "$unit" >/dev/null 2>&1 || true
  systemctl mask "$unit" >/dev/null 2>&1 || true
done

echo
echo "Interface configuration complete."
echo "- Hardware I2C is configured for bus 1."
echo "- Serial login/getty is disabled on ttyS0/ttyAMA0 so /dev/serial0 is reserved for the Arduino."

if [[ "$reboot_required" -eq 1 ]]; then
  echo
  echo "A reboot is required before the changes fully take effect."
else
  echo
  echo "No boot-config changes were needed."
fi
