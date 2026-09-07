#!/bin/bash
# setup-services.sh — Enable and start Acer Sense background services
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Setting up Acer Sense background services ==="

# 1. User service: mic-sync
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
mkdir -p "$USER_SYSTEMD_DIR"
cp -f "${ROOT_DIR}/data/mic-sync.service" "$USER_SYSTEMD_DIR/"
systemctl --user daemon-reload
systemctl --user enable --now mic-sync.service 2>/dev/null || true
echo "[OK] mic-sync.service enabled in user systemd."

# 2. System service: acer-fans
echo "Configuring acer-fans.service requires root privileges."
if [ "$(id -u)" -eq 0 ]; then
    cp -f "${ROOT_DIR}/data/acer-fans.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now acer-fans.service
    echo "[OK] acer-fans.service enabled and started."
else
    echo "To enable acer-fans.service, run:"
    echo "  sudo cp \"${ROOT_DIR}/data/acer-fans.service\" /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable --now acer-fans.service"
fi
