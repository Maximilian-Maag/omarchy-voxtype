# Design

## Boundary: the daemon owns recording; the plugin owns the desktop

voxtype is already a running service with a real control CLI. Re-implementing
recording, signals, or the IPC socket would duplicate the daemon and drift from it.
So the plugin is a thin, testable adapter:

- **Control** → shells out to `voxtype record <action>`.
- **State** → `voxtype status --format json`, falling back to the on-disk state file.
- **Presentation** → colours from the applied theme, mapped to semantic slots.
- **Desktop wiring** → keybindings + a theme-set hook.

## Testability without the daemon

The daemon boundary is a single injectable function, `run_capture(argv)`, and the
binary is resolved through `voxtype_bin()` which honours `$OMARCHY_VOXTYPE_BIN`:

- **Unit tests** mock `run_capture` and feed fixture state files — the daemon is
  never required.
- **Integration tests** put stub `voxtype` and `systemctl` first on `PATH` inside a
  throwaway `HOME`/`XDG_*`, then run the CLI as a subprocess.
- **e2e** runs a stateful fake daemon that actually maintains the dictation state
  machine, asserting the observable lifecycle.

This is the "inject/skip on absence" rule: nothing in the suite depends on the real
`voxtype.service` being up.

## Theme handling: read at runtime, never bake a palette

`colors.toml` is parsed as a small `key = "#hex"` map. States map to semantic slots:

| state | slot |
|-------|------|
| recording | `red` |
| transcribing | `yellow` |
| idle | `green` |
| paused | `orange` |
| error / unknown | `red` / `muted` |

Because the slots are read from whatever file is applied, **any** theme works. A
regression test asserts the CLI contains no six-digit hex literal, so nobody can
reintroduce a baked palette.

## Mutation testing

Two targets:

1. `bin/omarchy-voxtype` (python) — covered by unit + regression + integration.
2. `hooks/voxtype-theme-set` (shell) — covered by the hermetic shell test.

`tools/mutator.py` never lowers the threshold: a target whose tests fail on the
unmutated code is reported as an error, and a target that yields no mutants fails.
`tests/mutation.json` caps mutants (`max_mutants`) so the sample reaches the real
code deterministically.
