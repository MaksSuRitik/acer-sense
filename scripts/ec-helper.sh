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
if [ ! -w "$ec_path" ] && [ "${1:-}" != "get" ]; then
    echo "EC node $ec_path is not writable" >&2
    exit 1
fi

case "${1:-}" in
    80)
        printf "\x80" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
        ;;
    100)
        printf "\x00" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
        ;;
    get)
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
    usb:01|usb:1)
        printf "\x01" | dd of="$ec_path" bs=1 seek=239 count=1 conv=notrunc status=none
        ;;
    usb:00|usb:0)
        printf "\x00" | dd of="$ec_path" bs=1 seek=239 count=1 conv=notrunc status=none
        ;;
    raw:*)
        IFS=":" read -r _tag offset byte <<< "$1"
        if [ -n "$offset" ] && [ -n "$byte" ]; then
            printf "%b" "\\x${byte}" | dd of="$ec_path" bs=1 seek="$offset" count=1 conv=notrunc status=none
        fi
        ;;
    *)
        exit 2
        ;;
esac
