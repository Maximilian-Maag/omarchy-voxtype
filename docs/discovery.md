# Discovery — the real voxtype interface on this machine

Everything below was observed on the live machine before the plugin was designed, so
the CLI follows the daemon's **actual** interface rather than a guess.

## The daemon

```
$ command -v voxtype
/usr/bin/voxtype

$ systemctl --user status voxtype.service
● voxtype.service - Voxtype push-to-talk voice-to-text daemon
     Loaded: loaded (~/.config/systemd/user/voxtype.service; enabled)
     Active: active (running) since Tue 2026-10-06 19:31:01 CEST; 5 days ago
   Main PID: 1186 (voxtype)
             ├─1186 /usr/bin/voxtype daemon
             └─1495 /usr/lib/voxtype/voxtype-osd-gtk4
```

The unit file (`~/.config/systemd/user/voxtype.service`) is:

```ini
[Unit]
Description=Voxtype push-to-talk voice-to-text daemon
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/voxtype daemon
Restart=on-failure
RestartSec=5
Environment=XDG_RUNTIME_DIR=%t

[Install]
WantedBy=graphical-session.target
```

So the control lever for a restart is `systemctl --user try-restart voxtype.service`.

## The control interface (there IS a real toggle)

`voxtype --help` exposes `daemon`, `transcribe`, `config`, `info`, `status`,
`record`, `meeting`, `check-update`.

```
$ voxtype record --help
Control recording from external sources (compositor keybindings, scripts)
Commands:
  start   Start recording (send SIGUSR1 to daemon)
  stop    Stop recording and transcribe (send SIGUSR2 to daemon)
  toggle  Toggle recording state
  cancel  Cancel current recording or transcription (discard without output)
```

**Key finding:** a real toggle exists — `voxtype record toggle` — so the plugin drives
that instead of inventing one or sending `SIGUSR1/SIGUSR2` itself.

`voxtype status --format json` is the status surface:

```
$ voxtype status
idle

$ voxtype status --format json --extended
{"text": "🎙️", "alt": "idle", "class": "idle",
 "tooltip": "Voxtype ready - hold hotkey to record\nModel: base.en\nDevice: default\nBackend: CPU (AVX2)",
 "model": "base.en", "device": "default", "backend": "CPU (AVX2)"}
```

The `class` field is the canonical state (`idle`), and `text` is an icon.

## Runtime state

```
$ ls -la /run/user/1000/voxtype/
srwxr-xr-x audio.sock     <- the OSD/daemon IPC socket
-rw-r--r-- pid
-rw-r--r-- state          <- "idle" / "recording" / "transcribing"
-rw-r--r-- version
-rw-r--r-- voxtype.lock
```

The config file documents the state file explicitly:

> Use "auto" for default location ($XDG_RUNTIME_DIR/voxtype/state) … The daemon
> writes state ("idle", "recording", "transcribing") to this file whenever it
> changes. **Required for `voxtype record toggle` and `voxtype status` commands.**

The plugin reads this file as the no-daemon fallback, so `status` works in tests and
when the service is stopped.

## OSD and theming

```
$ voxtype info styles
OSD styles (Quickshell frontend)
  default ● active
  aegis-hud   /usr/share/voxtype/osd/aegis-hud

$ voxtype config schema | grep -A2 osd.palette
  osd.palette
    type    omarchy | fallback | package | custom
    notes   needs restart
    Where Quickshell recipes take their colors from.
```

**Key finding:** `osd.palette = omarchy` is what makes the OSD follow the applied
Omarchy theme — and the schema says the change **needs restart**. That is exactly the
job of the theme-set hook: stamp the theme, and (opt-in) restart the daemon so a
long-lived OSD repaints. `install.sh` sets `osd.palette omarchy` once.

## The applied theme path

```
$ cat ~/.local/state/omarchy/current/theme/colors.toml
mode = "dark"
accent = "#82FB9C"
background = "#0B0C16"
foreground = "#ddf7ff"
red = "#50f872"
yellow = "#50f7d4"
...
$ omarchy theme current
Hackerman
```

The path is a **copy** under a fixed `theme` directory — the theme *name* is not in
the path. The plugin reads this file at runtime for colours and records the name via
the hook, so no palette is ever baked in.

## Hook naming

`omarchy hook install theme-set <file>` copies to `~/.config/omarchy/hooks/theme-set.d/<basename>`.
Other plugins already install `calendar-theme-set`, `contacts-theme-set`, etc. A bare
`hooks/theme-set` would collide; this plugin installs **`voxtype-theme-set`**.

## What could NOT be verified

- **A live OSD repaint.** Changing `osd.palette`/restarting the daemon repaints the
  on-screen OSD, but the OSD only shows during recording; the plugin's own tests
  verify the *mechanism* (systemctl restart / config set), not the pixels.
- **A live keybinding press.** `bin/bindings.lua` uses the compositor's `hl`/`o`
  globals, which are absent in a test harness; its shape is pinned by regression
  tests and by `omarchy plugin validate`, and it mirrors the in-tree
  `~/.config/hypr/bindings.lua` conventions.
