#!/bin/bash
# power-cycle.sh — Cycle power profiles for Acer Sense (Fn+F / XF86Reload)
set -eu

curr="$(powerprofilesctl get 2>/dev/null || echo "balanced")"
if [ "$curr" = "power-saver" ]; then
    next="balanced"
elif [ "$curr" = "balanced" ]; then
    next="performance"
else
    next="power-saver"
fi

powerprofilesctl set "$next" 2>/dev/null || true

if command -v notify-send >/dev/null 2>&1; then
    case "$next" in
        power-saver)  msg="Бесшумно" ;;
        balanced)     msg="Обычный" ;;
        performance)  msg="Производительность" ;;
        *)            msg="$next" ;;
    esac
    notify-send -a "Acer Sense" -t 2000 "Профиль питания" "$msg" 2>/dev/null || true
fi
