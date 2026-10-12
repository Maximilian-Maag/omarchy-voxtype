"""Integration tests — the shipped CLI driven as a subprocess against a STUB voxtype.

We never touch the real daemon (or the real compositor): a fake ``voxtype`` and
``systemctl`` are placed first on PATH inside a throwaway HOME/XDG, and the CLI is
invoked exactly as a user would.
"""

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "bin/omarchy-voxtype"

STUB_VOXTYPE = """#!/bin/bash
# Stub voxtype for integration tests — records its argv and replays canned output.
printf '%s\\n' "$*" >> "$VOXTYPE_STUB_LOG"
case "$1" in
  status) cat "$VOXTYPE_STUB_STATUS" ;;
  record) exit "${VOXTYPE_STUB_RECORD_RC:-0}" ;;
  config) exit 0 ;;
esac
exit 0
"""

STUB_SYSTEMCTL = """#!/bin/bash
printf '%s\\n' "$*" >> "$SYSTEMCTL_STUB_LOG"
exit 0
"""


class CliIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = pathlib.Path(self.tmp.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.log = self.home / "voxtype.log"
        self.syslog = self.home / "systemctl.log"
        self.status = self.home / "status.json"
        self.status.write_text('{"text": "R", "alt": "idle", "class": "recording",'
                               ' "tooltip": "recording", "model": "base.en"}')
        self._stub("voxtype", STUB_VOXTYPE)
        self._stub("systemctl", STUB_SYSTEMCTL)
        self.env = {
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.home / "state"),
            "XDG_RUNTIME_DIR": str(self.home / "run"),
            "XDG_CONFIG_HOME": str(self.home / "config"),
            "VOXTYPE_STUB_LOG": str(self.log),
            "VOXTYPE_STUB_STATUS": str(self.status),
            "SYSTEMCTL_STUB_LOG": str(self.syslog),
        }
        (self.home / "run" / "voxtype").mkdir(parents=True)

    def _stub(self, name, body):
        p = self.bin / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args],
                              capture_output=True, text=True, env=self.env)

    def test_status_reads_daemon_json(self):
        r = self.run_cli("status", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["state"], "recording")
        self.assertEqual(data["source"], "daemon")

    def test_toggle_sends_record_toggle(self):
        r = self.run_cli("toggle")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("record toggle", self.log.read_text())

    def test_start_and_stop(self):
        self.run_cli("start")
        self.run_cli("stop")
        logged = self.log.read_text()
        self.assertIn("record start", logged)
        self.assertIn("record stop", logged)

    def test_cancel(self):
        self.run_cli("cancel")
        self.assertIn("record cancel", self.log.read_text())

    def test_record_failure_propagates(self):
        env = dict(self.env, VOXTYPE_STUB_RECORD_RC="4")
        r = subprocess.run([sys.executable, str(CLI), "toggle"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 4)

    def test_status_falls_back_to_state_file(self):
        (self.home / "run" / "voxtype" / "state").write_text("transcribing\n")
        empty = self.home / "empty-bin"
        empty.mkdir()
        env = dict(self.env, PATH=str(empty))    # no voxtype on PATH at all
        r = subprocess.run([sys.executable, str(CLI), "status", "--json"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["source"], "state-file")
        self.assertEqual(data["state"], "transcribing")

    def test_reload_calls_systemctl_try_restart(self):
        r = self.run_cli("reload")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--user try-restart voxtype.service", self.syslog.read_text())

    def test_theme_reads_applied_colors_toml(self):
        theme = self.home / "state" / "omarchy/current/theme"
        theme.mkdir(parents=True)
        (theme / "colors.toml").write_text('accent = "#abcdef"\nred = "#ff0000"\n')
        r = self.run_cli("theme", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["colors"]["accent"], "#abcdef")

    def test_bindings_writes_lua(self):
        dest = self.home / "out/voxtype-bindings.lua"
        r = self.run_cli("bindings", "--write", str(dest))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("voxtype record toggle", dest.read_text())

    def test_info_json(self):
        r = self.run_cli("info", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["plugin"], "Maximilian-Maag.voxtype")

    def test_unknown_command_exits_2(self):
        r = self.run_cli("nonsense")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
