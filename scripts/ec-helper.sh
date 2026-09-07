#!/bin/bash
set -eu

# Ensure debugfs is mounted
if [ ! -d /sys/kernel/debug/ec ]; then
    mount -t debugfs none /sys/kernel/debug 2>/dev/null || true
fi

# Ensure ec_sys is loaded with write_support=1
if [ ! -w /sys/kernel/debug/ec/ec0/io ]; then
    modprobe -r ec_sys 2>/dev/null || true
    modprobe ec_sys write_support=1 2>/dev/null || true
fi

ec_path=/sys/kernel/debug/ec/ec0/io

case "${1:-}" in
    80)
        # Direct EC register 221 (0xDD) -> 80% charge limit
        if [ -w "$ec_path" ]; then
            printf "\x80" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
        fi
        # Sysfs fallback if exposed by kernel
        for bat in /sys/class/power_supply/BAT*; do
            if [ -w "$bat/charge_control_end_threshold" ]; then
                echo 80 > "$bat/charge_control_end_threshold" 2>/dev/null || true
            fi
        done
        ;;
    100)
        # Direct EC register 221 (0xDD) -> 100% full charge
        if [ -w "$ec_path" ]; then
            printf "\x00" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
        fi
        # Sysfs fallback if exposed by kernel
        for bat in /sys/class/power_supply/BAT*; do
            if [ -w "$bat/charge_control_end_threshold" ]; then
                echo 100 > "$bat/charge_control_end_threshold" 2>/dev/null || true
            fi
        done
        ;;
    auto-limit*|auto:*)
        target="${2:-${1#*:}}"
        target="${target:-80}"
        # Determine battery capacity
        cap=0
        for bat in /sys/class/power_supply/BAT*; do
            if [ -r "$bat/capacity" ]; then
                cap=$(cat "$bat/capacity" 2>/dev/null || echo 0)
                break
            fi
        done
        if [ "$target" = "80" ]; then
            if [ "$cap" -ge 80 ]; then
                if [ -w "$ec_path" ]; then
                    printf "\x80" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
                fi
                echo "applied:stop (cap $cap >= 80)"
            elif [ "$cap" -le 78 ]; then
                if [ -w "$ec_path" ]; then
                    printf "\x00" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
                fi
                echo "applied:charge (cap $cap <= 78)"
            else
                echo "maintained:hysteresis (cap $cap)"
            fi
        else
            if [ -w "$ec_path" ]; then
                printf "\x00" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
            fi
            echo "applied:full (target 100)"
        fi
        ;;
    get)
        # Read current hardware limit from EC register 221 (0xDD)
        if [ -r "$ec_path" ]; then
            val=$(od -An -j221 -N1 -t x1 "$ec_path" 2>/dev/null | tr -d ' \n')
            if [ "$val" = "80" ]; then
                echo "80"
            elif [ "$val" = "00" ]; then
                echo "100"
            else
                echo "$val"
            fi
        else
            exit 1
        fi
        ;;
    cycles|cycle-count)
        # Read battery cycle count from EC register 244-245 (0xF4-0xF5)
        if [ -r "$ec_path" ]; then
            c=$(od -An -j244 -N2 -t u2 "$ec_path" 2>/dev/null | tr -d ' \n')
            if [ -n "$c" ] && [ "$c" -gt 0 ] && [ "$c" -lt 60000 ]; then
                echo "$c"
                exit 0
            fi
            c=$(od -An -j245 -N1 -t u1 "$ec_path" 2>/dev/null | tr -d ' \n')
            if [ -n "$c" ] && [ "$c" -gt 0 ]; then
                echo "$c"
                exit 0
            fi
        fi
        echo "0"
        ;;
    dump)
        if [ -r "$ec_path" ]; then
            xxd -g 1 -c 16 "$ec_path"
        fi
        ;;
    usb:01|usb:1)
        if [ -w "$ec_path" ]; then
            printf "\x01" | dd of="$ec_path" bs=1 seek=239 count=1 conv=notrunc status=none
        fi
        ;;
    usb:00|usb:0)
        if [ -w "$ec_path" ]; then
            printf "\x00" | dd of="$ec_path" bs=1 seek=239 count=1 conv=notrunc status=none
        fi
        ;;
    raw:*)
        IFS=":" read -r _tag offset byte <<< "$1"
        if [ -n "$offset" ] && [ -n "$byte" ] && [ -w "$ec_path" ]; then
            printf "%b" "\\x${byte}" | dd of="$ec_path" bs=1 seek="$offset" count=1 conv=notrunc status=none
        fi
        ;;
    *)
        exit 2
        ;;
esac
