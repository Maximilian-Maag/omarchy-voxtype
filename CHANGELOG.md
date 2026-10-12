# Changelog

All notable changes to omarchy-voxtype are documented here.

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
