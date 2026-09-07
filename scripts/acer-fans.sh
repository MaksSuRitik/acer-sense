#!/bin/bash
# acer-fans.sh — Fan profile sync for Acer laptops on Linux
# Применяет EC-профиль вентилятора и отслеживает смены профиля power-profiles-daemon через D-Bus.
set -euo pipefail

EC_PATH="/sys/kernel/debug/ec/ec0/io"

ec_write() {
    local byte="$1" offset="$2"
    printf "%b" "\\x${byte}" | dd of="$EC_PATH" bs=1 seek="$offset" count=1 conv=notrunc status=none
}

apply_fan_profile() {
    # Убеждаемся, что EC-файл доступен для записи (debugfs примонтирован и модуль ec_sys загружен)
    if [ ! -w "$EC_PATH" ]; then
        echo "acer-fans: EC path $EC_PATH not writable — is ec_sys module loaded?" >&2
        return 1
    fi

    case "$1" in
        power-saver)
            ec_write "02" 16
            ec_write "01" 45
            ;;
        balanced)
            ec_write "00" 16
            ec_write "01" 45
            ;;
        performance)
            ec_write "03" 16
            ec_write "00" 45
            ;;
        *)
            echo "acer-fans: unknown profile '$1', falling back to balanced" >&2
            ec_write "00" 16
            ec_write "01" 45
            ;;
    esac
    echo "acer-fans: applied profile '$1'"
}

# Применить профиль при запуске
INITIAL_PROFILE="$(powerprofilesctl get 2>/dev/null || echo balanced)"
apply_fan_profile "$INITIAL_PROFILE"

# Слушать изменения профиля через D-Bus без буферизации
exec stdbuf -oL dbus-monitor --system \
    "type='signal',interface='org.freedesktop.DBus.Properties',member='PropertiesChanged',path='/net/hadess/PowerProfiles'" 2>/dev/null \
    | grep --line-buffered "ActiveProfile\|net.hadess.PowerProfiles" \
    | while IFS= read -r _line; do
        sleep 0.15
        NEW_PROFILE="$(powerprofilesctl get 2>/dev/null || echo balanced)"
        apply_fan_profile "$NEW_PROFILE"
    done
