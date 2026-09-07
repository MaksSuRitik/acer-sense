#!/bin/bash
set -eu

ec_path=/sys/kernel/debug/ec/ec0/io
[ -w "$ec_path" ] || exit 1

case "${1:-}" in
    80) printf "\x80" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none ;;
    100) printf "\x00" | dd of="$ec_path" bs=1 seek=221 count=1 conv=notrunc status=none ;;
    *) exit 2 ;;
esac
