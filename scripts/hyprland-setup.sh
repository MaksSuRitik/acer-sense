#!/bin/bash
# hyprland-setup.sh — Idempotent Hyprland keybind installer for Acer Sense
# Configures:
#   XF86Launch6 -> Microphone toggle + LED sync
#   XF86Reload  -> Cycle power profiles (Fn+F)
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

# Using Lua [[ ... ]] literal brackets to avoid quote escaping and syntax errors with $
read -r -d '' LUA_BLOCK << 'EOF' || true
-- === Acer Sense keybinds ===
hl.unbind("XF86Reload")
hl.bind("XF86Reload", hl.dsp.exec_cmd([[sh -c 'if [ -x /usr/lib/acer-sense/scripts/power-cycle.sh ]; then /usr/lib/acer-sense/scripts/power-cycle.sh; elif [ -x "$HOME/.config/hypr/power-cycle.sh" ]; then "$HOME/.config/hypr/power-cycle.sh"; else curr=$(powerprofilesctl get 2>/dev/null || echo balanced); if [ "$curr" = "power-saver" ]; then powerprofilesctl set balanced; elif [ "$curr" = "balanced" ]; then powerprofilesctl set performance; else powerprofilesctl set power-saver; fi; fi']]), { description = "Acer Sense: Cycle power profile (Fn+F)" })
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
    # Remove any previous Acer Sense section if present
    if grep -qF "$SECTION_START" "$LUA_DMS_BINDS" 2>/dev/null; then
        sed -i "/$SECTION_START/,/$SECTION_END/d" "$LUA_DMS_BINDS"
    fi
    printf "\n%s\n" "$LUA_BLOCK" >> "$LUA_DMS_BINDS"
    echo "hyprland-setup: installed binds into $LUA_DMS_BINDS"
    installed=1
fi

# 2. Main hyprland.lua if present and binds not installed in dms
if [ "$installed" -eq 0 ] && [ -f "$LUA_MAIN" ]; then
    if grep -qF "$SECTION_START" "$LUA_MAIN" 2>/dev/null; then
        sed -i "/$SECTION_START/,/$SECTION_END/d" "$LUA_MAIN"
    fi
    printf "\n%s\n" "$LUA_BLOCK" >> "$LUA_MAIN"
    echo "hyprland-setup: installed binds into $LUA_MAIN"
    installed=1
fi

# 3. Caelestia Lua
if [ "$installed" -eq 0 ] && [ -f "$CAELESTIA_LUA" ]; then
    if grep -qF "$SECTION_START" "$CAELESTIA_LUA" 2>/dev/null; then
        sed -i "/$SECTION_START/,/$SECTION_END/d" "$CAELESTIA_LUA"
    fi
    printf "\n%s\n" "$LUA_BLOCK" >> "$CAELESTIA_LUA"
    echo "hyprland-setup: installed binds into $CAELESTIA_LUA"
    installed=1
fi

# 4. Standard hyprland.conf
if [ -f "$HYPR_CONF" ]; then
    if grep -qF "$CONF_SECTION_START" "$HYPR_CONF" 2>/dev/null; then
        sed -i "/$CONF_SECTION_START/,/$CONF_SECTION_END/d" "$HYPR_CONF"
    fi
    printf "\n%s\n" "$CONF_BLOCK" >> "$HYPR_CONF"
    echo "hyprland-setup: installed binds into $HYPR_CONF"
    installed=1
fi

if command -v hyprctl >/dev/null 2>&1; then
    hyprctl reload >/dev/null 2>&1 || true
    echo "hyprland-setup: reloaded Hyprland configuration."
fi
