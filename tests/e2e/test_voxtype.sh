#!/bin/bash
# e2e: stand up a stateful fake voxtype daemon and drive the shipped CLI against it,
# asserting the observable dictation lifecycle. Never touches the real daemon/session.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLI="$ROOT/bin/omarchy-voxtype"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

export HOME="$WORK/home"; mkdir -p "$HOME"
export XDG_STATE_HOME="$HOME/.local/state"
export XDG_RUNTIME_DIR="$WORK/run"
export XDG_CONFIG_HOME="$HOME/.config"
mkdir -p "$XDG_RUNTIME_DIR/voxtype"
STUB_BIN="$WORK/bin"; mkdir -p "$STUB_BIN"
export VOX_STATE_FILE="$XDG_RUNTIME_DIR/voxtype/state"
export PATH="$STUB_BIN:$PATH"

# A fake voxtype that actually maintains the state machine through its real CLI verb.
cat > "$STUB_BIN/voxtype" <<'EOF'
#!/bin/bash
case "$1" in
  status)
    state="$(cat "$VOX_STATE_FILE" 2>/dev/null || echo idle)"
    if [[ " $* " == *" --format json "* ]]; then
      printf '{"text":"x","alt":"%s","class":"%s","tooltip":"stub daemon"}\n' "$state" "$state"
    else
      printf '%s\n' "$state"
    fi
    ;;
  record)
    case "$2" in
      toggle) if [[ "$(cat "$VOX_STATE_FILE" 2>/dev/null)" == recording ]]; then echo idle > "$VOX_STATE_FILE"; else echo recording > "$VOX_STATE_FILE"; fi ;;
      start) echo recording > "$VOX_STATE_FILE" ;;
      stop) echo transcribing > "$VOX_STATE_FILE" ;;
      cancel) echo idle > "$VOX_STATE_FILE" ;;
    esac ;;
esac
exit 0
EOF
chmod +x "$STUB_BIN/voxtype"

# An applied theme, so the status line is genuinely themed.
mkdir -p "$XDG_STATE_HOME/omarchy/current/theme"
printf 'accent = "#abcdef"\nred = "#ff5555"\ngreen = "#50fa7b"\n' \
  > "$XDG_STATE_HOME/omarchy/current/theme/colors.toml"

fail=0
json_state() { "$CLI" status --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["state"])'; }
check() { if [[ "$2" == "$3" ]]; then echo "  ok: $1 ($2)"; else echo "  FAIL: $1 expected $3 got $2"; fail=1; fi; }

echo "start: $(json_state)"
check "idle at start"        "$(json_state)" "idle"

"$CLI" toggle >/dev/null 2>&1
check "after toggle"          "$(json_state)" "recording"

"$CLI" toggle >/dev/null 2>&1
check "toggle back to idle"   "$(json_state)" "idle"

"$CLI" start >/dev/null 2>&1
check "after start"           "$(json_state)" "recording"

"$CLI" stop >/dev/null 2>&1
check "after stop"            "$(json_state)" "transcribing"

"$CLI" cancel >/dev/null 2>&1
check "after cancel"          "$(json_state)" "idle"

# The status line is themed from the applied colors.toml (red for recording).
"$CLI" start >/dev/null 2>&1
line="$("$CLI" status)"
echo "$line"
check "recording line is themed red" "$([[ $line == *$'\033[38;2;255;85;85m'* ]] && echo yes || echo no)" "yes"

# bindings emit a Lua module carrying the real control verbs.
out="$WORK/voxtype-bindings.lua"
"$CLI" bindings --write "$out" >/dev/null 2>&1
check "bindings written"      "$([[ -s $out ]] && echo yes || echo no)" "yes"
check "bindings drive toggle" "$(grep -qc 'voxtype record toggle' "$out" && echo yes || echo no)" "yes"

echo
if (( fail == 0 )); then echo "e2e: all checks passed"; exit 0; else echo "e2e: FAILED"; exit 1; fi
