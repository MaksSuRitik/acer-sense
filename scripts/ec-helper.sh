#!/bin/bash
set -eu

ec_path=/sys/kernel/debug/ec/ec0/io
[ -w "$ec_path" ] || exit 1

case "${1:-}" in
    80)
        printf "\x80" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
        ;;
    100)
        printf "\x00" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none
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
