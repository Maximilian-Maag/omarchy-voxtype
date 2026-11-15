#!/bin/bash
# omarchy-voxtype install script. Run once after cloning, or re-run to update:
#
#   ./install.sh             install / update everything
#   ./install.sh --uninstall remove exactly what an install added, and only that
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN_DIR="${OMARCHY_VOXTYPE_BIN:-/usr/local/bin}"
BIN_SRC="$PLUGIN_DIR/bin/omarchy-voxtype"
BIN_DEST="$BIN_DIR/omarchy-voxtype"
HYPR_CONFIG_DIR="$CONFIG_DIR/hypr"
HYPR_MAIN="$HYPR_CONFIG_DIR/hyprland.lua"
FRAGMENT="$HYPR_CONFIG_DIR/voxtype-bindings.lua"
REQUIRE_LINE='require("hypr.voxtype-bindings")'
KEYBIND_MARKER='-- omarchy-voxtype keybindings'
HOOK_DEST="$CONFIG_DIR/omarchy/hooks/theme-set.d/voxtype-theme-set"

# ── remove_block: take the appended require block back out of a file ───────────
# Rebuilt line by line, never `sed -i`: the user's config is only ever rewritten
# one block smaller, and nothing is asked to interpret the rest of the file. The
# installer appends the line as a block — a blank line, a `-- omarchy-voxtype`
# marker comment, then the line — so all three come back out together; leaving the
# marker (and its blank line) behind would stack a new one on every install cycle.
remove_block() {  # remove_block <file> <line> <marker>
  local file="$1" line="$2" marker="$3"
  [[ -f $file ]] || return 0
  grep -qF -- "$line" "$file" || return 0
  local kept l
  kept="$(mktemp)"
  local -a lines=() out=()
  mapfile -t lines < "$file"
  for l in "${lines[@]}"; do
    if [[ $l == "$line" ]]; then
      if (( ${#out[@]} )) && [[ ${out[-1]} == "$marker" ]]; then
        unset 'out[-1]'
        if (( ${#out[@]} )) && [[ -z ${out[-1]} ]]; then
          unset 'out[-1]'
        fi
      fi
      continue
    fi
    out+=("$l")
  done
  for l in ${out[@]+"${out[@]}"}; do
    printf '%s\n' "$l"
  done > "$kept"
  mv "$kept" "$file"
}

# ── Uninstall ─────────────────────────────────────────────────────────────────
# Removes exactly the artifacts an install adds — the /usr/local/bin symlink, the
# bindings fragment, the require block in hyprland.lua, and the theme-set hook —
# and nothing else. A target that is not ours is left alone; voxtype's own config
# and the packages it depends on are never touched from here.
uninstall() {
  echo "omarchy-voxtype: uninstalling"

  # Only our own symlink goes: a real file, or a link to somewhere else, is left.
  if [[ -L $BIN_DEST ]] && [[ "$(readlink -f "$BIN_DEST")" == "$(readlink -f "$BIN_SRC")" ]]; then
    if (( EUID == 0 )); then
      rm -f "$BIN_DEST" && echo "  Removed $BIN_DEST."
    elif command -v sudo >/dev/null 2>&1; then
      sudo rm -f "$BIN_DEST" && echo "  Removed $BIN_DEST."
    else
      echo "  WARNING: no sudo — remove $BIN_DEST manually."
    fi
  elif [[ -e $BIN_DEST ]]; then
    echo "  WARNING: $BIN_DEST is not a link into this checkout — left alone."
  fi

  if [[ -f $FRAGMENT ]]; then
    if cmp -s "$PLUGIN_DIR/bin/bindings.lua" "$FRAGMENT"; then
      rm -f "$FRAGMENT"
      echo "  Removed the bindings fragment: $FRAGMENT"
    else
      echo "  WARNING: $FRAGMENT is not the shipped copy — left alone."
    fi
  fi

  if [[ -f $HYPR_MAIN ]] && grep -qF -- "$REQUIRE_LINE" "$HYPR_MAIN"; then
    remove_block "$HYPR_MAIN" "$REQUIRE_LINE" "$KEYBIND_MARKER"
    echo "  Took the require line back out of $HYPR_MAIN"
  fi

  if [[ -f $HOOK_DEST ]]; then
    rm -f "$HOOK_DEST"
    echo "  Removed the theme-set hook ($HOOK_DEST)"
  fi

  echo ""
  echo "Done. Reload Hyprland config for the keybindings:  hyprctl reload"
}

if [[ ${1:-} == --uninstall ]]; then
  uninstall
  exit 0
fi

echo "omarchy-voxtype: installing from $PLUGIN_DIR"

# ── 1. Validate the plugin ────────────────────────────────────────────────────
if command -v omarchy >/dev/null 2>&1; then
  omarchy plugin validate "$PLUGIN_DIR" && echo "  manifest OK."
fi

# ── 2. Put the CLI on PATH (symlink, so git pull keeps it current) ────────────
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
echo "The OSD repaints on a theme switch only when config/voxtype.json sets"
echo "reload_on_theme_change (or OMARCHY_VOXTYPE_RELOAD=1 overrides it)."
