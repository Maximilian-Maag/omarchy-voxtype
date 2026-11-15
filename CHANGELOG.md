# Changelog

All notable changes to omarchy-voxtype are documented here.

## [0.1.7] — 2026-11-15

### Fixed
- **`paused` rendered uncoloured on themes without `orange`** (#7). `STATE_COLOR`
  mapped `paused` to the palette key `orange`, which 4 of the 23 shipped Omarchy
  themes do not define, so `style()` found no colour and the paused status line came
  out plain there. `paused` now maps to `accent` (present in every theme), and
  `state_color` falls back through `muted`/`foreground`/`accent` — then to any colour
  present — so no state can resolve to nothing. Unit tests assert every state's key
  resolves against a palette that has no `orange`.

## [0.1.6] — 2026-11-15

### Fixed
- **The colour parser and the renderer disagreed on hex lengths** (#6). `parse_colors`
  accepted any 3-8 digit hex while `style()` dropped anything shorter than 6 chars and
  truncated longer values (silently discarding alpha), so a colour the parser reported as
  present could render unthemed. Both now share `normalize_hex`: `#rgb`/`#rgba` expand to
  six digits and any alpha channel is dropped, so exactly the colours the parser accepts
  are the ones the renderer can draw (`#abc` -> `#aabbcc`, `#abcd` -> `#aabbcc`,
  `#0f0f0f00` -> `#0f0f0f`). Unit tests cover each form and assert parser/renderer
  agreement.

## [0.1.5] — 2026-11-15

### Fixed
- **A quoted `reload_on_theme_change` could turn the restart ON** (#5). The flag was
  coerced with `bool()`, so any non-empty string — `"false"`, `"no"`, `"0"` — was
  truthy and *enabled* the theme-change restart that `reload_enabled()` gates, the
  opposite of intent. It is now coerced strictly: real booleans and the strings
  `true/false/yes/no/1/0` (case- and space-insensitive) are honoured and anything
  else falls back to the safe default, off. Unit tests pin every variant.

## [0.1.4] — 2026-11-15

### Fixed
- **The config's `reload_on_theme_change` did nothing** (#1). `bin/omarchy-voxtype` loaded
  the key but nothing read it — only the theme-set hook's `OMARCHY_VOXTYPE_RELOAD`
  environment variable had any effect — and the sibling `notify` key was likewise only
  echoed. `reload_on_theme_change` now actually controls the reload: `reload --if-enabled`
  (what the hook calls) restarts the daemon only when the config enables it or
  `OMARCHY_VOXTYPE_RELOAD=1` overrides; a bare `reload` still always restarts, so the
  manual command is unchanged. The `notify` key had no consumer and could not be wired
  without inventing a notification subsystem, so it was removed. Unit, integration and
  shell tests pin the config-driven reload end-to-end: a hook run with
  `reload_on_theme_change: true` restarts the daemon, with `false` it leaves it alone.

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
