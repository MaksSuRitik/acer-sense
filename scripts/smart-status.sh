#!/bin/bash
set -eu

device="${1:-}"
case "$device" in
    /dev/sd[a-z]|/dev/sd[a-z][a-z]|/dev/nvme[0-9]n[0-9]|/dev/mmcblk[0-9]) ;;
    *) exit 2 ;;
esac

smartctl_path="$(command -v smartctl || true)"
[ -n "$smartctl_path" ] || exit 127
exec "$smartctl_path" -a -n standby "$device"
