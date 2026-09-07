#!/bin/bash
# mic-sync.sh — Microphone mute toggle + hardware LED sync via hda-verb
set -eu

if [ "${1:-}" = "toggle" ]; then
    wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle 2>/dev/null || true
    sleep 0.05
else
    sleep 2
fi

# Locate first valid HDA device with GPIO control
HDA_DEV=""
for dev in /dev/snd/hwC*D*; do
    if [ -c "$dev" ]; then
        HDA_DEV="$dev"
        break
    fi
done

if [ -n "$HDA_DEV" ] && command -v hda-verb >/dev/null 2>&1; then
    hda-verb "$HDA_DEV" 0x01 SET_GPIO_MASK 0x04 >/dev/null 2>&1 || sudo hda-verb "$HDA_DEV" 0x01 SET_GPIO_MASK 0x04 >/dev/null 2>&1 || true
    hda-verb "$HDA_DEV" 0x01 SET_GPIO_DIRECTION 0x04 >/dev/null 2>&1 || sudo hda-verb "$HDA_DEV" 0x01 SET_GPIO_DIRECTION 0x04 >/dev/null 2>&1 || true

    if wpctl get-volume @DEFAULT_AUDIO_SOURCE@ 2>/dev/null | grep -q "MUTED"; then
        hda-verb "$HDA_DEV" 0x01 SET_GPIO_DATA 0x04 >/dev/null 2>&1 || sudo hda-verb "$HDA_DEV" 0x01 SET_GPIO_DATA 0x04 >/dev/null 2>&1 || true
    else
        hda-verb "$HDA_DEV" 0x01 SET_GPIO_DATA 0x00 >/dev/null 2>&1 || sudo hda-verb "$HDA_DEV" 0x01 SET_GPIO_DATA 0x00 >/dev/null 2>&1 || true
    fi
fi
