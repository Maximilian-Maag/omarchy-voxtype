#!/bin/bash
# Shell tests for hooks/voxtype-theme-set — run hermetically with a throwaway HOME/XDG.
#
# The hook is what gets copied into ~/.config/omarchy/hooks/theme-set.d/, so the tests
# also cover the two traps: it must write the normalised theme, and — because an
# installed hook cannot see its plugin — it must self-locate, not use $BASH_SOURCE/..
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOK="$ROOT/hooks/voxtype-theme-set"
pass=0; fail=0
ok()  { echo "  ok: $*"; pass=$((pass+1)); }
bad() { echo "  FAIL: $*"; fail=$((fail+1)); }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# A PATH with stub `systemctl` (and nothing else that matters) so the hook never
# touches the real session.
STUB_BIN="$WORK/bin"
mkdir -p "$STUB_BIN"
cat > "$STUB_BIN/systemctl" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "$SYSCTL_LOG"
exit 1
EOF
chmod +x "$STUB_BIN/systemctl"

sandbox() {
  HOME="$WORK/home-$1"; export HOME
  mkdir -p "$HOME"
  XDG_STATE_HOME="$HOME/.local/state"; export XDG_STATE_HOME
  XDG_CONFIG_HOME="$HOME/.config"; export XDG_CONFIG_HOME
  export PATH="$STUB_BIN:$PATH"
  export SYSCTL_LOG="$HOME/sysctl.log"
  : > "$SYSCTL_LOG"
  unset OMARCHY_VOXTYPE_RELOAD OMARCHY_VOXTYPE_DIR 2>/dev/null || true
}

# 1. a theme name writes the normalised state file
sandbox 1
bash "$HOOK" "Tokyo Night"
STATE="$XDG_STATE_HOME/omarchy-voxtype/active-theme"
if [[ -f $STATE ]] && [[ "$(cat "$STATE")" == "tokyo-night" ]]; then
  ok "theme written normalised"
else
  bad "theme state file wrong (got: $(cat "$STATE" 2>/dev/null))"
fi

# 2. no argument is a no-op (nothing written, exit status 0)
sandbox 2
bash "$HOOK"
rc=$?
if [[ ! -e "$XDG_STATE_HOME/omarchy-voxtype/active-theme" ]] && (( rc == 0 )); then
  ok "empty theme is a no-op (exit 0)"
else
  bad "empty theme: file written or wrong exit (rc=$rc)"
fi

# 3. default: a theme switch does NOT restart the daemon (repaint is opt-in)
sandbox 3
bash "$HOOK" "Gruvbox"
rc=$?
if [[ ! -s $SYSCTL_LOG ]] && (( rc == 0 )); then
  ok "default run leaves the daemon alone (exit 0)"
else
  bad "default run reloaded (rc=$rc): $(cat "$SYSCTL_LOG")"
fi

# 4. reload enabled: the hook self-locates its plugin and calls the plugin's CLI,
#    and swallows the CLI's failure (`|| true`) — the hook must still exit 0.
sandbox 4
FAKE="$WORK/fake-plugin"
mkdir -p "$FAKE/bin"
cat > "$FAKE/bin/omarchy-voxtype" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "$CLI_LOG"
exit 1
EOF
chmod +x "$FAKE/bin/omarchy-voxtype"
export OMARCHY_VOXTYPE_DIR="$FAKE"
export OMARCHY_VOXTYPE_RELOAD=1
export CLI_LOG="$HOME/cli.log"
: > "$CLI_LOG"
bash "$HOOK" "Nord"
rc=$?
if [[ -s $CLI_LOG ]] && [[ ! -s $SYSCTL_LOG ]] && (( rc == 0 )); then
  ok "reload enabled: plugin CLI called, its failure swallowed ($(cat "$CLI_LOG"))"
else
  bad "reload/cli: cli=$(cat "$CLI_LOG" 2>/dev/null) sysctl=$(cat "$SYSCTL_LOG") rc=$rc"
fi

# 5. reload enabled but no plugin resolvable: fall back to systemctl, and swallow its
#    failure too (the stub exits 1) — the hook must still exit 0.
sandbox 5
export OMARCHY_VOXTYPE_DIR="$WORK/does-not-exist"
export OMARCHY_VOXTYPE_RELOAD=1
bash "$HOOK" "Everforest"
rc=$?
if [[ -s $SYSCTL_LOG ]] && (( rc == 0 )); then
  ok "reload fallback restarts voxtype.service and survives its failure"
else
  bad "reload fallback: sysctl=$(cat "$SYSCTL_LOG") rc=$rc"
fi

echo
if (( fail == 0 )); then echo "shell: all $pass passed"; exit 0; else echo "shell: $fail failed"; exit 1; fi
