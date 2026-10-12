# omarchy-voxtype

An [Omarchy](https://omarchy.org/) plugin that wires the **voxtype** push-to-talk
voice-to-text daemon into the Hyprland desktop — a theme-aware status line,
compositor keybindings, and a theme-set hook that keeps voxtype's OSD on the applied
palette.

## Why

voxtype already runs as a systemd **user** service (`voxtype.service`) and speaks a
real control interface. What it leaves to the desktop is (a) a status view that
follows the *applied* Omarchy theme, (b) keybindings, and (c) repainting its OSD when
the theme changes. This plugin adds exactly that — and re-implements **none** of the
recording. There is nothing to guess: the daemon is already on the machine.

## Real interface used (verified on this machine)

| What | How |
|------|-----|
| State | `voxtype status [--format json] [--extended]` |
| Control | `voxtype record start\|stop\|toggle\|cancel` |
| Config | `voxtype config get\|set\|schema` |
| Runtime | socket `/run/user/$UID/voxtype/audio.sock`, state file `.../voxtype/state` |

The plugin shells out to these; it never sends signals itself and never opens the
socket directly. See [`docs/discovery.md`](docs/discovery.md) for the full findings.

## Usage

```bash
omarchy-voxtype status            # themed state line (🎙️ voxtype: idle)
omarchy-voxtype status --json     # {state, icon, tooltip, theme, color, source}
omarchy-voxtype toggle            # start/stop dictation  (voxtype record toggle)
omarchy-voxtype start | stop | cancel
omarchy-voxtype theme --json      # the applied palette
omarchy-voxtype bindings          # emit the Hyprland Lua module
omarchy-voxtype info --json       # integration summary
omarchy-voxtype doctor            # diagnose what is (not) working
omarchy-voxtype reload            # restart the daemon so the OSD repaints
```

## Theme awareness

The status line is coloured from the **applied** theme:
`~/.local/state/omarchy/current/theme/colors.toml`. That path is a *copy* under a
fixed `theme` directory, so the theme name is not in the path — `omarchy-voxtype
theme` reports the name the theme-set hook last recorded. No palette is hardcoded, so
all stock themes (and your own) work.

## Keybindings

| Key | Action |
|-----|--------|
| `Super+Ctrl+X` | Push to talk (toggle) |
| `Super+Ctrl+Shift+X` | Discard the current dictation |
| `Super+Ctrl+Alt+X` | Show the theme-aware status |

Keys are configurable in `config/voxtype.json` (copied to
`~/.local/state/omarchy-voxtype/config.json` on install).

## Requirements

- Omarchy (Hyprland) with **voxtype** installed and, for live control, the
  `voxtype.service` user unit running.
- Python 3 (system interpreter).

## Installation

```bash
omarchy plugin add https://github.com/Maximilian-Maag/omarchy-voxtype.git --enable
bash ~/.config/omarchy/plugins/Maximilian-Maag.voxtype/install.sh
```

Or from a clone: `bash install.sh`.

## The theme-set hook, and its two traps

`install.sh` runs `omarchy hook install theme-set hooks/voxtype-theme-set`.
`omarchy hook install` copies to the file's **basename**, so shipping a bare
`hooks/theme-set` would silently clobber another plugin's hook. This plugin ships
`hooks/voxtype-theme-set`. Once installed, the hook cannot find its plugin via
`$(dirname "$BASH_SOURCE")/..` (that is the hooks dir), so it **self-locates** over
`$OMARCHY_VOXTYPE_DIR`, the installed plugins dir, and a dev checkout.

Repainting the OSD restarts the daemon (which reloads the transcription model), so it
is opt-in: `OMARCHY_VOXTYPE_RELOAD=1`.

## Development

```bash
make check      # policy + unit + regression (fast)
make test       # the full suite, including measured mutation testing (~10 min)
SKIP_MUTATION=1 bash tools/run_tests.sh   # everything except mutation
```

## License

MIT — see [LICENSE](LICENSE).
