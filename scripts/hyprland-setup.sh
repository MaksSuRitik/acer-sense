#!/bin/bash
# hyprland-setup.sh — Idempotent Hyprland keybind installer for Acer Sense
# Configures:
#   XF86Reload  -> Cycle power profiles (Fn+F)
#   XF86Launch6 -> Microphone mute toggle + LED sync
set -eu

USER_HOME="${HOME:-/home/$(id -un)}"

LUA_DMS_BINDS="${USER_HOME}/.config/hypr/dms/binds-user.lua"
LUA_MAIN="${USER_HOME}/.config/hypr/hyprland.lua"
CAELESTIA_LUA="${USER_HOME}/.config/caelestia/hypr-user.lua"
HYPR_CONF="${USER_HOME}/.config/hypr/hyprland.conf"

SECTION_START="-- === Acer Sense keybinds ==="
SECTION_END="-- === /Acer Sense keybinds ==="

CONF_SECTION_START="# === Acer Sense keybinds ==="
CONF_SECTION_END="# === /Acer Sense keybinds ==="

read -r -d '' LUA_BLOCK << 'EOF' || true
-- === Acer Sense keybinds ===
hl.unbind("XF86Reload")
hl.bind("XF86Reload", hl.dsp.exec_cmd([[sh -c 'if [ -x /usr/lib/acer-sense/scripts/power-cycle.sh ]; then /usr/lib/acer-sense/scripts/power-cycle.sh; elif [ -x "$HOME/.config/hypr/power-cycle.sh" ]; then "$HOME/.config/hypr/power-cycle.sh"; else curr=$(powerprofilesctl get 2>/dev/null || echo balanced); if [ "$curr" = "power-saver" ]; then powerprofilesctl set balanced; elif [ "$curr" = "balanced" ]; then powerprofilesctl set performance; else powerprofilesctl set power-saver; fi; fi']]), { description = "Acer Sense: Cycle power profile (Fn+F)" })
hl.unbind("XF86Launch6")
hl.bind("XF86Launch6", hl.dsp.exec_cmd([[sh -c 'if [ -x /usr/lib/acer-sense/scripts/mic-sync.sh ]; then /usr/lib/acer-sense/scripts/mic-sync.sh toggle; elif [ -x "$HOME/.config/hypr/mic-sync.sh" ]; then "$HOME/.config/hypr/mic-sync.sh" toggle; fi']]), { description = "Acer Sense: Toggle microphone" })
-- === /Acer Sense keybinds ===
EOF

read -r -d '' CONF_BLOCK << 'EOF' || true
# === Acer Sense keybinds ===
bind = , XF86Reload,  exec, /usr/lib/acer-sense/scripts/power-cycle.sh
bind = , XF86Launch6, exec, /usr/lib/acer-sense/scripts/mic-sync.sh toggle
# === /Acer Sense keybinds ===
EOF

installed=0

# 1. Hyprland DMS Lua config
if [ -f "$LUA_DMS_BINDS" ]; then
    # Remove existing section if present
    if grep -qF "$SECTION_START" "$LUA_DMS_BINDS" 2>/dev/null; then
        sed -i "/$SECTION_START/,/$SECTION_END/d" "$LUA_DMS_BINDS"
    fi
    # Also clean up standalone XF86Launch6 if it was added manually outside
    sed -i '/hl\.unbind("XF86Launch6")/d' "$LUA_DMS_BINDS"
    sed -i '/hl\.bind("XF86Launch6",/d' "$LUA_DMS_BINDS"

    printf "\n%s\n" "$LUA_BLOCK" >> "$LUA_DMS_BINDS"
    echo "hyprland-setup: installed both keybinds into $LUA_DMS_BINDS"
    installed=1
fi

# 2. Main hyprland.lua if present and binds not installed in dms
if [ "$installed" -eq 0 ] && [ -f "$LUA_MAIN" ]; then
    if grep -qF "$SECTION_START" "$LUA_MAIN" 2>/dev/null; then
        sed -i "/$SECTION_START/,/$SECTION_END/d" "$LUA_MAIN"
    fi
    printf "\n%s\n" "$LUA_BLOCK" >> "$LUA_MAIN"
    echo "hyprland-setup: installed both keybinds into $LUA_MAIN"
    installed=1
fi

# 3. Caelestia Lua
if [ "$installed" -eq 0 ] && [ -f "$CAELESTIA_LUA" ]; then
    if grep -qF "$SECTION_START" "$CAELESTIA_LUA" 2>/dev/null; then
        sed -i "/$SECTION_START/,/$SECTION_END/d" "$CAELESTIA_LUA"
    fi
    printf "\n%s\n" "$LUA_BLOCK" >> "$CAELESTIA_LUA"
    echo "hyprland-setup: installed both keybinds into $CAELESTIA_LUA"
    installed=1
fi

# 4. Standard hyprland.conf
if [ -f "$HYPR_CONF" ]; then
    if grep -qF "$CONF_SECTION_START" "$HYPR_CONF" 2>/dev/null; then
        sed -i "/$CONF_SECTION_START/,/$CONF_SECTION_END/d" "$HYPR_CONF"
    fi
    printf "\n%s\n" "$CONF_BLOCK" >> "$HYPR_CONF"
    echo "hyprland-setup: installed both keybinds into $HYPR_CONF"
    installed=1
fi

if command -v hyprctl >/dev/null 2>&1; then
    hyprctl reload >/dev/null 2>&1 || true
    echo "hyprland-setup: reloaded Hyprland configuration."
fi
