#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Installing lgpio native prerequisites..."
sudo apt update
sudo apt install -y wget unzip swig build-essential python3-dev python3-setuptools

echo "Downloading and installing the lg archive..."
cd "$TMP_DIR"
wget -q http://abyz.me.uk/lg/lg.zip
unzip -q lg.zip
cd lg
make
sudo make install
sudo ldconfig

echo "lg native library installed."
