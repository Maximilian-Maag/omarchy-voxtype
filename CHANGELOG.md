# Changelog

All notable changes to omarchy-voxtype are documented here.

## [0.1.3] — 2026-11-15

### Fixed
- **The shipped `config/voxtype.json` had no reader** (#2). The CLI defaulted `--config`
  to `~/.local/state/omarchy-voxtype/config.json` — a path `install.sh` never creates — so
  the shipped config was dead, while the README claimed install copied a file nothing
  wrote. The CLI now reads the config shipped beside it (`<plugin>/config/voxtype.json`,
  resolved through the installed symlink), matching how this repo's other plugins consume
  their `config/<name>.json`. A regression test runs a relocated copy of the CLI against
  its own `config/voxtype.json` and asserts the shipped binding is what gets emitted.

## [0.1.2] — 2026-11-15

### Removed
- **The dead `slugify()` helper and its unit test** (#4). It was defined and unit-tested
  but never called anywhere in the CLI. The one place a theme name is normalised now does
  so inline in `omarchy_theme_name()` (the same `.strip().lower().replace(" ", "-")` form
  the sibling plugins use), so the standalone helper was removed.

## [0.1.1] — 2026-11-15

### Fixed
- **The applied theme name was read from a stale hook stamp** (#3). `active_theme()`
  trusted `<state>/omarchy-voxtype/active-theme` — written only by the theme-set hook —
  instead of Omarchy's authoritative `<state>/omarchy/current/theme.name`, which is
  rewritten on every theme change with no dependency on this hook. A stamp left stale by
  a hook that did not run reported the wrong name as truth. Resolution is now
  `current/theme.name` → the hook stamp. Unit + regression tests pin that the live name
  wins over a stale stamp.

## [0.1.0] — 2026-10-12

### Added
- **`omarchy-voxtype` CLI** that drives the already-running `voxtype.service`
  (systemd user unit) through its **real** control interface — `voxtype record
  start|stop|toggle|cancel` — rather than re-implementing recording. Commands:
  `status`, `toggle`, `start`, `stop`, `cancel`, `reload`, `theme`, `bindings`,
  `info`, `doctor`.
- **Theme-aware status.** Colours are read at runtime from
  `~/.local/state/omarchy/current/theme/colors.toml` (the *applied* theme) — no
  palette is baked in, so every theme works with no per-theme code. The state maps
  to theme slots (recording → `red`, transcribing → `yellow`, idle → `green`).
- **Hyprland keybindings** (`bin/bindings.lua`): `Super+Ctrl+X` push-to-talk toggle,
  `Super+Ctrl+Shift+X` cancel, `Super+Ctrl+Alt+X` status.
- **`hooks/voxtype-theme-set`** — a *uniquely named* theme-set hook. `omarchy hook
  install` names installed hooks by basename, so a bare `hooks/theme-set` would
  clobber other plugins' hooks; this one installs as `voxtype-theme-set`. It stamps
  the active theme and (opt-in, `OMARCHY_VOXTYPE_RELOAD=1`) repaints the OSD by
  restarting the daemon. It self-locates its plugin (an installed hook cannot use
  `$(dirname "$BASH_SOURCE")/..`).
- **Graceful degradation.** Every entry point falls back to voxtype's on-disk state
  file and then to `unknown`; the daemon is never required for `status`, `bindings`
  or `theme`.
- Full test harness: unit, regression, integration (stub `voxtype`/`systemctl` on
  PATH), e2e (stateful fake daemon) and shell tests, plus measured mutation testing
  and policy as code.
