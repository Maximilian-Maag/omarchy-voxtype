#!/bin/bash
# omarchy-voxtype install script. Run once after cloning, or re-run to update.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "omarchy-voxtype: installing from $PLUGIN_DIR"

# ── 1. Validate the plugin ────────────────────────────────────────────────────
if command -v omarchy >/dev/null 2>&1; then
  omarchy plugin validate "$PLUGIN_DIR" && echo "  manifest OK."
fi

# ── 2. Put the CLI on PATH (symlink, so git pull keeps it current) ────────────
BIN_SRC="$PLUGIN_DIR/bin/omarchy-voxtype"
BIN_DEST="/usr/local/bin/omarchy-voxtype"
chmod +x "$BIN_SRC"
if [[ -L $BIN_DEST ]] && [[ "$(readlink -f "$BIN_DEST")" == "$(readlink -f "$BIN_SRC")" ]]; then
  echo "  omarchy-voxtype already on PATH."
elif (( EUID == 0 )); then
  ln -sf "$BIN_SRC" "$BIN_DEST" && echo "  Installed $BIN_DEST."
elif command -v sudo >/dev/null 2>&1; then
  sudo ln -sf "$BIN_SRC" "$BIN_DEST" && echo "  Installed $BIN_DEST."
else
  echo "  WARNING: no sudo — add $BIN_SRC to PATH manually."
fi

# ── 3. theme-set hook (uniquely named — see hooks/voxtype-theme-set) ──────────
chmod +x "$PLUGIN_DIR/hooks/voxtype-theme-set"
if command -v omarchy >/dev/null 2>&1; then
  omarchy hook install theme-set "$PLUGIN_DIR/hooks/voxtype-theme-set"
  echo "  Installed theme-set hook (voxtype-theme-set)."
fi

# ── 4. Wire the keybindings into Hyprland ─────────────────────────────────────
HYPR_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hypr"
HYPR_MAIN="$HYPR_CONFIG_DIR/hyprland.lua"
if [[ -f $HYPR_MAIN ]]; then
  cp "$PLUGIN_DIR/bin/bindings.lua" "$HYPR_CONFIG_DIR/voxtype-bindings.lua"
  if ! grep -q "voxtype-bindings" "$HYPR_MAIN"; then
    printf '\n-- omarchy-voxtype keybindings\nrequire("hypr.voxtype-bindings")\n' >> "$HYPR_MAIN"
    echo "  Wired keybindings into $HYPR_MAIN"
  else
    echo "  Keybindings already wired (updated)."
  fi
else
  echo "  WARNING: $HYPR_MAIN not found — add: require(\"hypr.voxtype-bindings\")"
fi

# ── 5. Make voxtype's OSD take its palette from the applied theme ─────────────
# `osd.palette = omarchy` is what makes every theme work with no per-theme code; the
# voxtype theme-set hook relies on it. Only set it when voxtype is present.
if command -v voxtype >/dev/null 2>&1; then
  voxtype config set osd.palette omarchy >/dev/null 2>&1 \
    && echo "  OSD palette set to 'omarchy' (follows the applied theme)."
fi

echo ""
echo "Done. Try:  omarchy-voxtype status   /   omarchy-voxtype toggle"
echo "The OSD repaints on a theme switch only when OMARCHY_VOXTYPE_RELOAD=1."
