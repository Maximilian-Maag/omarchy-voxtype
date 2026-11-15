#!/bin/bash
# The `--uninstall` contract, in a throwaway HOME/XDG with the desktop's commands
# stubbed — no package and no real session is ever touched.
#
# What is checked: a full install -> uninstall round-trip leaves the user's
# hyprland.lua byte-identical (sha256) and leaves no marker/blank line behind,
# removes exactly the artifacts the install added (the CLI symlink, the bindings
# fragment, the theme-set hook), leaves a foreign file alone, and never touches
# voxtype's own config.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
INSTALL="$REPO/install.sh"
ORIG_PATH="$PATH"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass=0
fail=0
ok()  { printf '  ok    %s\n' "$1"; pass=$((pass + 1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail + 1)); }
check()         { if [[ $2 == "$3" ]]; then ok "$1"; else bad "$1 (expected '$2', got '$3')"; fi; }
check_file()    { if [[ -f $1 ]]; then ok "$2"; else bad "$2 (no file: $1)"; fi; }
check_no_file() { if [[ -e $1 ]]; then bad "$2 (still there: $1)"; else ok "$2"; fi; }

HOME_FAKE="$TMP/home"; CONFIG="$TMP/config"; BIN="$TMP/bin"; LOG="$TMP/stub.log"
mkdir -p "$HOME_FAKE" "$CONFIG/hypr" "$BIN"

write_stub() { printf '#!/bin/bash\n%s\n' "$2" > "$BIN/$1"; chmod 755 "$BIN/$1"; }

write_stub sudo 'echo "sudo $*" >> "$STUB_LOG"; exec "$@"'
# omarchy: validate is a no-op, and hook install copies the hook into theme-set.d
# exactly as the real command does.
write_stub omarchy '
echo "omarchy $*" >> "$STUB_LOG"
case "$1 $2" in
  "plugin validate") exit 0 ;;
  "hook install")
    mkdir -p "$XDG_CONFIG_HOME/omarchy/hooks/theme-set.d"
    cp "$4" "$XDG_CONFIG_HOME/omarchy/hooks/theme-set.d/$(basename "$4")" 2>/dev/null || true
    exit 0 ;;
esac
exit 0'

run() {  # run [args...] — install.sh against the fake env, CLI symlink under $BIN
  env HOME="$HOME_FAKE" XDG_CONFIG_HOME="$CONFIG" PATH="$BIN:$ORIG_PATH" STUB_LOG="$LOG" \
    OMARCHY_VOXTYPE_BIN="$BIN" bash "$INSTALL" "$@"
}

REQ='require("hypr.voxtype-bindings")'
KBMARK='-- omarchy-voxtype keybindings'

seed_user_config() {
  printf -- '-- my own hyprland.lua\nhl.monitor({ output = "eDP-1" })\n' > "$CONFIG/hypr/hyprland.lua"
  rm -rf "$CONFIG/omarchy/hooks"
  rm -f "$CONFIG/hypr/voxtype-bindings.lua" "$BIN/omarchy-voxtype"
}

printf 'uninstall round-trip\n'

# ── the round-trip: install, then uninstall, and the user's config comes back ───
seed_user_config
before_hypr="$(sha256sum "$CONFIG/hypr/hyprland.lua" | cut -d' ' -f1)"

run >/dev/null 2>&1
check "installing succeeds" "0" "$?"
check "the CLI is linked into the bin directory" "$REPO/bin/omarchy-voxtype" "$(readlink -f "$BIN/omarchy-voxtype")"
check_file "$CONFIG/hypr/voxtype-bindings.lua" "install copies the bindings fragment"
check "install appends the require line once" "1" "$(grep -cF -- "$REQ" "$CONFIG/hypr/hyprland.lua")"
check_file "$CONFIG/omarchy/hooks/theme-set.d/voxtype-theme-set" "install installs the theme-set hook"

run --uninstall >"$TMP/out" 2>&1
check "uninstalling succeeds" "0" "$?"
check_no_file "$BIN/omarchy-voxtype" "the CLI symlink is gone"
check_no_file "$CONFIG/hypr/voxtype-bindings.lua" "the bindings fragment is gone"
check "the require line is gone" "0" "$(grep -cF -- "$REQ" "$CONFIG/hypr/hyprland.lua")"
check_no_file "$CONFIG/omarchy/hooks/theme-set.d/voxtype-theme-set" "the theme-set hook is gone"
check "the user's hyprland.lua is byte-identical to before" "$before_hypr" \
  "$(sha256sum "$CONFIG/hypr/hyprland.lua" | cut -d' ' -f1)"
check "no keybindings marker is left behind" "0" "$(grep -c -- "$KBMARK" "$CONFIG/hypr/hyprland.lua")"
check "the user's own line survives" "1" "$(grep -c -- '-- my own hyprland.lua' "$CONFIG/hypr/hyprland.lua")"

# ── foreign things are left alone ──────────────────────────────────────────────
# A file at the CLI path that is not our link.
seed_user_config
printf 'not a link\n' > "$BIN/omarchy-voxtype"
run --uninstall >"$TMP/out" 2>&1
check "uninstalling with a foreign CLI file succeeds" "0" "$?"
check_file "$BIN/omarchy-voxtype" "a non-link file at the CLI path is left alone"
check "and the refusal is reported" "1" "$(grep -cF -- 'is not a link into this checkout' "$TMP/out")"

# A bindings fragment that is not the shipped copy.
seed_user_config
printf -- '-- hand-written, not ours\n' > "$CONFIG/hypr/voxtype-bindings.lua"
run --uninstall >"$TMP/out" 2>&1
check_file "$CONFIG/hypr/voxtype-bindings.lua" "a bindings fragment that is not ours is left alone"
check "and the refusal is reported" "1" "$(grep -cF -- 'is not the shipped copy' "$TMP/out")"

# A foreign require line is not this script's to touch.
seed_user_config
printf -- '-- my own hyprland.lua\nrequire("hypr.my-own-bindings")\n' > "$CONFIG/hypr/hyprland.lua"
before="$(sha256sum "$CONFIG/hypr/hyprland.lua" | cut -d' ' -f1)"
run --uninstall >/dev/null 2>&1
check "a foreign require line leaves the config byte-identical" "$before" \
  "$(sha256sum "$CONFIG/hypr/hyprland.lua" | cut -d' ' -f1)"

# A config holding nothing but our line is cleaned up too.
seed_user_config
printf '%s\n' "$REQ" > "$CONFIG/hypr/hyprland.lua"
run --uninstall >/dev/null 2>&1
check "a config holding only our line is cleaned up" "0" "$(grep -cF -- "$REQ" "$CONFIG/hypr/hyprland.lua")"

# A second full cycle is still byte-identical — a stacked marker would show here.
seed_user_config
run >/dev/null 2>&1; run --uninstall >/dev/null 2>&1
run >/dev/null 2>&1; run --uninstall >/dev/null 2>&1
check "a second cycle leaves hyprland.lua byte-identical" "$before_hypr" \
  "$(sha256sum "$CONFIG/hypr/hyprland.lua" | cut -d' ' -f1)"

# voxtype's own config is not this script's to touch on the way out.
seed_user_config
run >/dev/null 2>&1
: > "$LOG"
run --uninstall >/dev/null 2>&1
check "no voxtype config is changed by --uninstall" "0" "$(grep -c -- 'config set' "$LOG")"

printf '\nuninstall round-trip: %d passed, %d failed\n' "$pass" "$fail"
(( fail == 0 ))
