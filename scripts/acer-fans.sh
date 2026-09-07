#!/bin/bash
apply_fan_profile() {
    case "$1" in
        power-saver)
            printf "\x02" | dd of=/sys/kernel/debug/ec/ec0/io bs=1 seek=16 count=1 conv=notrunc status=none[cite: 2, 4]
            printf "\x01" | dd of=/sys/kernel/debug/ec/ec0/io bs=1 seek=45 count=1 conv=notrunc status=none[cite: 2, 4]
            ;;
        balanced)
            printf "\x00" | dd of=/sys/kernel/debug/ec/ec0/io bs=1 seek=16 count=1 conv=notrunc status=none[cite: 2, 4]
            printf "\x01" | dd of=/sys/kernel/debug/ec/ec0/io bs=1 seek=45 count=1 conv=notrunc status=none[cite: 2, 4]
            ;;
        performance)
            printf "\x03" | dd of=/sys/kernel/debug/ec/ec0/io bs=1 seek=16 count=1 conv=notrunc status=none[cite: 2, 4]
            printf "\x00" | dd of=/sys/kernel/debug/ec/ec0/io bs=1 seek=45 count=1 conv=notrunc status=none[cite: 2, 4]
            ;;
    esac
}
apply_fan_profile "$(powerprofilesctl get)"[cite: 2, 4]

stdbuf -oL dbus-monitor --system "type='signal',interface='org.freedesktop.DBus.Properties',member='PropertiesChanged'" | \
grep --line-buffered "ActiveProfile" | \
while read -r line; do[cite: 2, 4]
    sleep 0.2[cite: 2, 4]
    new_profile=$(powerprofilesctl get)[cite: 2, 4]
    apply_fan_profile "$new_profile"[cite: 2, 4]
done[cite: 2, 4]
