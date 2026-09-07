#!/bin/bash
# acer-battery-monitor.sh — Acer Battery Charge Limit Hysteresis Daemon
#
# EC offset 221 (0xDD):
#   0x80 = Stop charging immediately (inhibit AC charge)
#   0x00 = Allow charging (normal AC charge)
#
# Hysteresis logic for 80% optimized charging:
#   - If battery capacity >= 80%: write 0x80 (cut off charging)
#   - If battery capacity <= 78%: write 0x00 (resume charging)
#   - If 79%: preserve current charging state (hysteresis deadband)
#   - If 100% full charge mode: write 0x00 (allow full charging)
set -euo pipefail

EC_PATH="/sys/kernel/debug/ec/ec0/io"
CONF_OVERRIDE="/etc/acer-sense/charge_limit"

ensure_ec_access() {
    if [ ! -d /sys/kernel/debug/ec ]; then
        mount -t debugfs none /sys/kernel/debug 2>/dev/null || true
    fi
    if [ ! -w "$EC_PATH" ]; then
        modprobe -r ec_sys 2>/dev/null || true
        modprobe ec_sys write_support=1 2>/dev/null || true
    fi
}

get_battery_capacity() {
    for bat in /sys/class/power_supply/BAT*; do
        if [ -r "$bat/capacity" ]; then
            cat "$bat/capacity" 2>/dev/null && return 0
        fi
    done
    echo "0"
}

get_target_limit() {
    # 1. Check system-wide override file
    if [ -r "$CONF_OVERRIDE" ]; then
        val=$(cat "$CONF_OVERRIDE" 2>/dev/null | tr -d ' \n\r')
        if [ "$val" = "80" ] || [ "$val" = "100" ]; then
            echo "$val"
            return 0
        fi
    fi

    # 2. Check user settings.json in /home/*/.config/acer-sense/settings.json
    for cfg in /home/*/.config/acer-sense/settings.json; do
        if [ -r "$cfg" ]; then
            val=$(grep -o '"charge_limit"[[:space:]]*:[[:space:]]*[0-9]*' "$cfg" 2>/dev/null | grep -o '[0-9]*' || true)
            if [ "$val" = "80" ] || [ "$val" = "100" ]; then
                echo "$val"
                return 0
            fi
        fi
    done

    # 3. Default to 100%
    echo "100"
}

get_current_ec_limit() {
    if [ -r "$EC_PATH" ]; then
        val=$(od -An -j221 -N1 -t x1 "$EC_PATH" 2>/dev/null | tr -d ' \n')
        echo "$val"
    else
        echo "unknown"
    fi
}

apply_ec_byte() {
    local hex="$1"
    ensure_ec_access
    if [ -w "$EC_PATH" ]; then
        printf "%b" "\\x${hex}" | dd of="$EC_PATH" bs=1 seek=221 count=1 conv=notrunc status=none
    else
        echo "acer-battery-monitor: cannot write to $EC_PATH" >&2
        return 1
    fi
}

check_and_apply() {
    local target="${1:-$(get_target_limit)}"
    local cap
    cap=$(get_battery_capacity)
    local cur_ec
    cur_ec=$(get_current_ec_limit)

    if [ "$target" = "80" ]; then
        if [ "$cap" -ge 80 ]; then
            # Battery reached or exceeded 80% -> stop charge
            if [ "$cur_ec" != "80" ]; then
                apply_ec_byte "80"
                echo "acer-battery-monitor: battery at ${cap}% >= 80% — charging stopped (EC 221 = 0x80)"
            fi
        elif [ "$cap" -le 78 ]; then
            # Battery dropped to 78% or below -> resume charge
            if [ "$cur_ec" != "00" ]; then
                apply_ec_byte "00"
                echo "acer-battery-monitor: battery at ${cap}% <= 78% — charging resumed (EC 221 = 0x00)"
            fi
        else
            # 79% hysteresis band: do not alter state
            echo "acer-battery-monitor: battery at ${cap}% (hysteresis band) — state maintained (EC 221 = 0x${cur_ec})"
        fi
    else
        # 100% mode -> always allow full charging
        if [ "$cur_ec" != "00" ]; then
            apply_ec_byte "00"
            echo "acer-battery-monitor: target 100% — charging enabled (EC 221 = 0x00)"
        fi
    fi
}

case "${1:-}" in
    --once|-1)
        check_and_apply "${2:-}"
        ;;
    --status)
        cap=$(get_battery_capacity)
        tgt=$(get_target_limit)
        cur=$(get_current_ec_limit)
        echo "Battery Capacity : ${cap}%"
        echo "Config Target    : ${tgt}%"
        echo "EC 221 Register  : 0x${cur} ($([ "$cur" = "80" ] && echo "charging inhibited" || echo "charging enabled"))"
        ;;
    --daemon|-d|"")
        echo "acer-battery-monitor: starting background hysteresis loop (interval 10s)..."
        while true; do
            check_and_apply "" || true
            sleep 10
        done
        ;;
    *)
        echo "Usage: $0 [--once [80|100] | --daemon | --status]"
        exit 1
        ;;
esac
