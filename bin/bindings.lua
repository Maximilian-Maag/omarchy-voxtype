-- Hyprland keybindings added by omarchy-voxtype.
-- Sourced from hyprland.lua by install.sh (require("hypr.voxtype-bindings")).
--
-- voxtype's hotkey is configured in Hyprland (its own config defaults to
-- Super+Ctrl+X for push-to-talk). These bindings drive the daemon through its real
-- control interface (`voxtype record …`), so they never re-implement recording.

-- Push to talk: toggle recording on/off.
hl.unbind("SUPER + CTRL + X")
o.bind("SUPER + CTRL + X", "Push to talk (voxtype)", "voxtype record toggle")

-- Discard the current recording/transcription without output.
hl.unbind("SUPER + CTRL + SHIFT + X")
o.bind("SUPER + CTRL + SHIFT + X", "voxtype: discard dictation", "voxtype record cancel")

-- Show the daemon state, coloured from the applied Omarchy theme.
hl.unbind("SUPER + CTRL + ALT + X")
o.bind("SUPER + CTRL + ALT + X", "voxtype status",
       "omarchy-voxtype status; echo; echo 'Press Enter to close.'; read")
