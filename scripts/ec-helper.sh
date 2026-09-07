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
        # 1. WMI driver interface if available
        for p in /sys/bus/wmi/drivers/acer-wmi-battery/health_mode \
                 /sys/devices/platform/acer-wmi/health_mode; do
            if [ -w "$p" ]; then
                echo 1 > "$p" 2>/dev/null || true
            fi
        done
        # 2. Sysfs battery threshold
        for bat in /sys/class/power_supply/BAT*; do
            if [ -w "$bat/charge_control_end_threshold" ]; then
                echo 80 > "$bat/charge_control_end_threshold" 2>/dev/null || true
            fi
        done
        # 3. Direct EC register 221 (0xDD)
        if [ -w "$ec_path" ]; then
            printf "\x80" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
        fi
        ;;
    100)
        # 1. WMI driver interface if available
        for p in /sys/bus/wmi/drivers/acer-wmi-battery/health_mode \
                 /sys/devices/platform/acer-wmi/health_mode; do
            if [ -w "$p" ]; then
                echo 0 > "$p" 2>/dev/null || true
            fi
        done
        # 2. Sysfs battery threshold
        for bat in /sys/class/power_supply/BAT*; do
            if [ -w "$bat/charge_control_end_threshold" ]; then
                echo 100 > "$bat/charge_control_end_threshold" 2>/dev/null || true
            fi
        done
        # 3. Direct EC register 221 (0xDD)
        if [ -w "$ec_path" ]; then
            printf "\x00" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
        fi
        ;;
    get)
        # 1. Check WMI driver if present
        for p in /sys/bus/wmi/drivers/acer-wmi-battery/health_mode \
                 /sys/devices/platform/acer-wmi/health_mode; do
            if [ -r "$p" ]; then
                val=$(cat "$p" 2>/dev/null | tr -d ' \n')
                if [ "$val" = "1" ]; then
                    echo "80"
                    exit 0
                elif [ "$val" = "0" ]; then
                    echo "100"
                    exit 0
                fi
            fi
        done
        # 2. Check EC register 221 (0xDD)
        if [ -r "$ec_path" ]; then
            val=$(od -An -j221 -N1 -t x1 "$ec_path" | tr -d ' \n')
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
