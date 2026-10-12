"""Unit tests for omarchy-voxtype's pure logic.

The shipped CLI has no ``.py`` extension (it installs as ``omarchy-voxtype``), so it
is loaded with a SourceFileLoader rather than imported by name.

None of these tests require the voxtype daemon to be running: the daemon boundary
(``run_capture``) is mocked, and the state file is a fixture.
"""

import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import unittest
import unittest.mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "bin/omarchy-voxtype"

_loader = importlib.machinery.SourceFileLoader("omarchy_voxtype", str(CLI))
_spec = importlib.util.spec_from_loader("omarchy_voxtype", _loader)
vox = importlib.util.module_from_spec(_spec)
_loader.exec_module(vox)


class Completed:
    """A stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class EnvCase(unittest.TestCase):
    """Restore the environment and cwd-ish globals after each test."""

    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)


class TestSlugify(EnvCase):
    def test_title_case_to_dir_name(self):
        self.assertEqual(vox.slugify("Yellow On Black"), "yellow-on-black")

    def test_collapses_and_trims_whitespace(self):
        self.assertEqual(vox.slugify("  Tokyo   Night  "), "tokyo-night")

    def test_already_slug_is_unchanged(self):
        self.assertEqual(vox.slugify("hackerman"), "hackerman")


class TestParseColors(EnvCase):
    def test_reads_hex_values_only(self):
        colors = vox.parse_colors('mode = "dark"\naccent = "#82FB9C"\nred = "#50f872"\n')
        self.assertEqual(colors, {"accent": "#82FB9C", "red": "#50f872"})

    def test_ignores_comments_and_non_colours(self):
        text = "# a comment\nmode = \"dark\"\nborder = \"rgba(1,2,3,4)\"\n"
        self.assertEqual(vox.parse_colors(text), {})

    def test_strips_quotes(self):
        self.assertEqual(vox.parse_colors("accent = '#abc'\n"), {"accent": "#abc"})

    def test_empty_text(self):
        self.assertEqual(vox.parse_colors(""), {})


class TestLoadTheme(EnvCase):
    def test_missing_file_is_empty(self):
        self.assertEqual(vox.load_theme("/nonexistent/colors.toml"), {})

    def test_fixture(self):
        self.assertEqual(vox.load_theme(ROOT / "tests/fixtures/colors.toml"),
                         {"accent": "#abcdef", "background": "#010203"})

    def test_default_path_uses_state_home(self):
        tmp = pathlib.Path(self.enterContext(_tmp()))
        state = tmp / "state"
        (state / vox.THEME_COLORS).parent.mkdir(parents=True)
        (state / vox.THEME_COLORS).write_text('accent = "#123456"\n')
        os.environ["XDG_STATE_HOME"] = str(state)
        self.assertEqual(vox.load_theme(), {"accent": "#123456"})


class TestActiveTheme(EnvCase):
    def test_records_what_the_hook_wrote(self):
        tmp = pathlib.Path(self.enterContext(_tmp()))
        os.environ["XDG_STATE_HOME"] = str(tmp)
        d = tmp / "omarchy-voxtype"
        d.mkdir(parents=True)
        (d / "active-theme").write_text("tokyo-night\n")
        self.assertEqual(vox.active_theme(), "tokyo-night")

    def test_absent_is_empty(self):
        os.environ["XDG_STATE_HOME"] = "/nonexistent"
        self.assertEqual(vox.active_theme(), "")


class TestEnvironment(EnvCase):
    def test_runtime_dir_from_env(self):
        os.environ["XDG_RUNTIME_DIR"] = "/run/user/1000"
        self.assertEqual(str(vox.runtime_dir()), "/run/user/1000/voxtype")

    def test_runtime_dir_absent(self):
        os.environ.pop("XDG_RUNTIME_DIR", None)
        self.assertIsNone(vox.runtime_dir())
        self.assertIsNone(vox.state_file_path())

    def test_state_file_path(self):
        os.environ["XDG_RUNTIME_DIR"] = "/run/user/1000"
        self.assertEqual(str(vox.state_file_path()), "/run/user/1000/voxtype/state")

    def test_voxtype_bin_override(self):
        os.environ["OMARCHY_VOXTYPE_BIN"] = "/opt/voxtype"
        self.assertEqual(vox.voxtype_bin(), "/opt/voxtype")

    def test_state_home_default(self):
        os.environ.pop("XDG_STATE_HOME", None)
        self.assertTrue(str(vox.state_home()).endswith("/.local/state"))


class TestState(EnvCase):
    def test_normalize_known(self):
        for state in vox.KNOWN_STATES:
            self.assertEqual(vox.normalize_state(state.upper()), state)

    def test_normalize_trims(self):
        self.assertEqual(vox.normalize_state("  idle\n"), "idle")

    def test_normalize_unknown(self):
        self.assertEqual(vox.normalize_state("bogus"), vox.FALLBACK_STATE)
        self.assertEqual(vox.normalize_state(""), vox.FALLBACK_STATE)
        self.assertEqual(vox.normalize_state(None), vox.FALLBACK_STATE)

    def test_read_state_fixture(self):
        p = pathlib.Path(self.enterContext(_tmp())) / "state"
        p.write_text("recording")
        self.assertEqual(vox.read_state(p), "recording")

    def test_read_state_missing(self):
        self.assertEqual(vox.read_state("/nonexistent/state"), vox.FALLBACK_STATE)

    def test_read_state_none_path_without_runtime(self):
        os.environ.pop("XDG_RUNTIME_DIR", None)
        self.assertEqual(vox.read_state(), vox.FALLBACK_STATE)


class TestParseStatusJson(EnvCase):
    def test_uses_class(self):
        out = vox.parse_status_json('{"text": "X", "alt": "idle", "class": "recording"}')
        self.assertEqual(out["state"], "recording")
        self.assertEqual(out["icon"], "X")

    def test_falls_back_to_alt(self):
        out = vox.parse_status_json('{"alt": "transcribing"}')
        self.assertEqual(out["state"], "transcribing")
        # the icon falls back to the state's icon when the daemon sends no "text"
        self.assertEqual(out["icon"], vox.ICONS["transcribing"])

    def test_missing_tooltip_is_empty_string(self):
        out = vox.parse_status_json('{"class": "idle"}')
        self.assertEqual(out["tooltip"], "")

    def test_extended_fields(self):
        out = vox.parse_status_json(
            '{"class": "idle", "text": "Y", "tooltip": "t", "model": "base.en",'
            ' "device": "default", "backend": "CPU"}')
        self.assertEqual(out["model"], "base.en")
        self.assertEqual(out["device"], "default")
        self.assertEqual(out["backend"], "CPU")

    def test_invalid_json_is_empty(self):
        self.assertEqual(vox.parse_status_json("not json"), {})

    def test_non_dict_is_empty(self):
        self.assertEqual(vox.parse_status_json("[1, 2, 3]"), {})

    def test_unknown_class_becomes_unknown(self):
        self.assertEqual(vox.parse_status_json('{"class": "zzz"}')["state"],
                         vox.FALLBACK_STATE)


class TestPresentation(EnvCase):
    def test_style_wraps_truecolour(self):
        self.assertEqual(vox.style("hi", "#ff0000", True), "\033[38;2;255;0;0mhi\033[0m")

    def test_style_other_channel(self):
        self.assertEqual(vox.style("x", "#00ff00", True), "\033[38;2;0;255;0mx\033[0m")

    def test_style_disabled(self):
        self.assertEqual(vox.style("hi", "#ff0000", False), "hi")

    def test_style_without_colour(self):
        self.assertEqual(vox.style("hi", None, True), "hi")

    def test_style_short_hex_is_passthrough(self):
        self.assertEqual(vox.style("hi", "#abc", True), "hi")

    def test_state_color(self):
        colors = {"red": "#ff0000", "green": "#00ff00", "muted": "#888888"}
        self.assertEqual(vox.state_color("recording", colors), "#ff0000")
        self.assertEqual(vox.state_color("idle", colors), "#00ff00")

    def test_state_color_unknown_key_falls_back_to_muted(self):
        self.assertEqual(vox.state_color("bogus", {"muted": "#111111"}), "#111111")

    def test_format_status_no_colour(self):
        self.assertEqual(vox.format_status("idle", {}, color=False), "🎙️ voxtype: idle")

    def test_format_status_colours_by_default(self):
        out = vox.format_status("recording", {"red": "#ff0000"})
        self.assertIn("\033[38;2;255;0;0m", out)
        self.assertIn("voxtype: recording", out)


class TestConfig(EnvCase):
    def test_defaults(self):
        os.environ["XDG_STATE_HOME"] = "/nonexistent"
        cfg = vox.load_config()
        self.assertEqual(cfg["bindings"]["toggle"], "SUPER + CTRL + X")
        self.assertFalse(cfg["reload_on_theme_change"])
        self.assertTrue(cfg["notify"])

    def test_file_overrides_bindings_and_merge_partial(self):
        p = pathlib.Path(self.enterContext(_tmp())) / "config.json"
        p.write_text(json.dumps({"bindings": {"toggle": "SUPER + V"}, "notify": False}))
        cfg = vox.load_config(p)
        self.assertEqual(cfg["bindings"]["toggle"], "SUPER + V")
        self.assertEqual(cfg["bindings"]["cancel"], vox.DEFAULT_BINDINGS["cancel"])
        self.assertFalse(cfg["notify"])

    def test_bad_json_falls_back_to_defaults(self):
        p = pathlib.Path(self.enterContext(_tmp())) / "config.json"
        p.write_text("{not json")
        self.assertEqual(vox.load_config(p)["bindings"], dict(vox.DEFAULT_BINDINGS))


class TestBindingsLua(EnvCase):
    def test_contains_all_three_keys(self):
        text = vox.bindings_lua()
        self.assertIn("hl.unbind(\"SUPER + CTRL + X\")", text)
        self.assertIn("voxtype record toggle", text)
        self.assertIn("voxtype record cancel", text)
        self.assertIn("omarchy-voxtype status", text)

    def test_honours_custom_key(self):
        text = vox.bindings_lua({"bindings": {"toggle": "SUPER + V"}})
        self.assertIn("SUPER + V", text)
        self.assertNotIn("SUPER + CTRL + X", text)

    def test_ends_with_newline(self):
        self.assertTrue(vox.bindings_lua().endswith("\n"))


class TestControlInterface(EnvCase):
    def test_record_argv(self):
        os.environ["OMARCHY_VOXTYPE_BIN"] = "/opt/voxtype"
        self.assertEqual(vox.record_argv("toggle"), ["/opt/voxtype", "record", "toggle"])

    def test_systemctl_argv(self):
        self.assertEqual(vox.systemctl_argv("try-restart", "voxtype.service"),
                         ["systemctl", "--user", "try-restart", "voxtype.service"])

    def test_run_capture_absent_binary_is_none(self):
        self.assertIsNone(vox.run_capture(["/nonexistent/binary-xyz"]))

    def test_run_capture_returns_process(self):
        proc = vox.run_capture(["/bin/echo", "hello"])
        self.assertIsNotNone(proc)
        self.assertEqual(proc.returncode, 0)
        # stdout must be captured AND decoded to str (text=True, capture_output=True)
        self.assertEqual(proc.stdout, "hello\n")


class TestDaemonState(EnvCase):
    def test_uses_daemon_json(self):
        seen = {}

        def fake(argv):
            seen["argv"] = argv
            return Completed(0, '{"class": "recording", "text": "R"}')

        with unittest.mock.patch.object(vox, "run_capture", side_effect=fake):
            info = vox.daemon_state()
        self.assertEqual(info["state"], "recording")
        self.assertEqual(info["source"], "daemon")
        self.assertNotIn("--extended", seen["argv"])

    def test_extended_adds_flag(self):
        seen = {}

        def fake(argv):
            seen["argv"] = argv
            return Completed(0, '{"class": "idle"}')

        with unittest.mock.patch.object(vox, "run_capture", side_effect=fake):
            vox.daemon_state(extended=True)
        self.assertIn("--extended", seen["argv"])

    def test_falls_back_to_state_file(self):
        tmp = pathlib.Path(self.enterContext(_tmp()))
        os.environ["XDG_RUNTIME_DIR"] = str(tmp)
        (tmp / "voxtype").mkdir()
        (tmp / "voxtype" / "state").write_text("transcribing")
        with unittest.mock.patch.object(vox, "run_capture", return_value=None):
            info = vox.daemon_state()
        self.assertEqual(info["source"], "state-file")
        self.assertEqual(info["state"], "transcribing")

    def test_falls_back_when_daemon_errors(self):
        tmp = pathlib.Path(self.enterContext(_tmp()))
        os.environ["XDG_RUNTIME_DIR"] = str(tmp)
        (tmp / "voxtype").mkdir()
        (tmp / "voxtype" / "state").write_text("idle")
        with unittest.mock.patch.object(vox, "run_capture",
                                        return_value=Completed(1, "", "boom")):
            info = vox.daemon_state()
        self.assertEqual(info["source"], "state-file")


class TestDoRecord(EnvCase):
    def test_success(self):
        with unittest.mock.patch.object(vox, "run_capture",
                                        return_value=Completed(0, "", "")) as m:
            self.assertEqual(vox.do_record("toggle"), 0)
        self.assertEqual(m.call_args[0][0][1:], ["record", "toggle"])

    def test_missing_binary(self):
        with unittest.mock.patch.object(vox, "run_capture", return_value=None):
            self.assertEqual(vox.do_record("start"), 1)

    def test_propagates_returncode(self):
        with unittest.mock.patch.object(vox, "run_capture",
                                        return_value=Completed(3, "", "")):
            self.assertEqual(vox.do_record("stop"), 3)


class TestDoReload(EnvCase):
    def _run(self):
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = vox.main(["reload"])
        return rc, buf.getvalue()

    def test_success_prints_and_returns_zero(self):
        with unittest.mock.patch.object(vox, "run_capture",
                                        return_value=Completed(0, "", "")):
            rc, out = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("restarted", out)

    def test_failure_returns_code_without_success_message(self):
        with unittest.mock.patch.object(vox, "run_capture",
                                        return_value=Completed(1, "", "")):
            rc, out = self._run()
        self.assertEqual(rc, 1)
        self.assertNotIn("restarted", out)

    def test_missing_systemctl(self):
        with unittest.mock.patch.object(vox, "run_capture", return_value=None):
            rc, _ = self._run()
        self.assertEqual(rc, 1)


class TestMainDispatch(EnvCase):
    def _run(self, argv):
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = vox.main(argv)
        return rc, buf.getvalue()

    def test_no_command_prints_help(self):
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            self.assertEqual(vox.main([]), 2)

    def test_status_json(self):
        with unittest.mock.patch.object(
                vox, "run_capture", return_value=Completed(0, '{"class": "idle"}')):
            rc, out = self._run(["status", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["state"], "idle")

    def test_status_state_file(self):
        p = pathlib.Path(self.enterContext(_tmp())) / "state"
        p.write_text("recording")
        rc, out = self._run(["status", "--state-file", str(p), "--no-color"])
        self.assertEqual(rc, 0)
        self.assertIn("recording", out)

    def test_status_extended_with_tooltip_prints_it(self):
        with unittest.mock.patch.object(
                vox, "run_capture",
                return_value=Completed(0, '{"class": "idle", "tooltip": "hello"}')):
            rc, out = self._run(["status", "--extended", "--no-color"])
        self.assertIn("hello", out)

    def test_status_extended_without_tooltip_prints_no_extra_line(self):
        with unittest.mock.patch.object(
                vox, "run_capture", return_value=Completed(0, '{"class": "idle"}')):
            rc, out = self._run(["status", "--extended", "--no-color"])
        self.assertEqual(out.count("\n"), 1)

    def test_status_without_extended_never_prints_the_tooltip(self):
        with unittest.mock.patch.object(
                vox, "run_capture",
                return_value=Completed(0, '{"class": "idle", "tooltip": "hello"}')):
            rc, out = self._run(["status", "--no-color"])
        self.assertNotIn("hello", out)

    def test_theme_json_fixture(self):
        rc, out = self._run(["theme", "--json", "--colors",
                             str(ROOT / "tests/fixtures/colors.toml")])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["colors"]["accent"], "#abcdef")

    def test_theme_missing_returns_1(self):
        rc, out = self._run(["theme", "--colors", "/nonexistent/colors.toml"])
        self.assertEqual(rc, 1)
        self.assertIn("no colors.toml", out)

    def test_theme_text_lists_colours(self):
        rc, out = self._run(["theme", "--no-color", "--colors",
                             str(ROOT / "tests/fixtures/colors.toml")])
        self.assertEqual(rc, 0)
        self.assertIn("2 colours", out)

    def test_bindings_text(self):
        rc, out = self._run(["bindings"])
        self.assertEqual(rc, 0)
        self.assertIn("voxtype record toggle", out)

    def test_bindings_json(self):
        rc, out = self._run(["bindings", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["toggle"], "SUPER + CTRL + X")

    def test_bindings_write(self):
        dest = pathlib.Path(self.enterContext(_tmp())) / "a/b/voxtype-bindings.lua"
        rc, out = self._run(["bindings", "--write", str(dest)])
        self.assertEqual(rc, 0)
        self.assertIn("voxtype record toggle", dest.read_text())

    def test_bindings_write_is_idempotent(self):
        dest = pathlib.Path(self.enterContext(_tmp())) / "a/b/voxtype-bindings.lua"
        self.assertEqual(self._run(["bindings", "--write", str(dest)])[0], 0)
        self.assertEqual(self._run(["bindings", "--write", str(dest)])[0], 0)

    def test_info_json(self):
        with unittest.mock.patch.object(
                vox, "run_capture", return_value=Completed(0, '{"class": "idle"}')):
            rc, out = self._run(["info", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["plugin"], vox.PLUGIN_ID)

    def test_doctor_json(self):
        os.environ.pop("XDG_RUNTIME_DIR", None)
        with unittest.mock.patch.object(vox, "run_capture", return_value=None):
            rc, out = self._run(["doctor", "--json"])
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["problems"])

    def test_doctor_daemon_answering_reports_no_fallback_problem(self):
        with unittest.mock.patch.object(
                vox, "run_capture", return_value=Completed(0, '{"class": "idle"}')):
            rc, out = self._run(["doctor", "--json"])
        self.assertEqual(rc, 0)
        self.assertNotIn("daemon not answering; using the on-disk state file",
                         json.loads(out)["problems"])

    def test_toggle_dispatches_record(self):
        with unittest.mock.patch.object(vox, "run_capture",
                                        return_value=Completed(0, "", "")) as m:
            rc = vox.main(["toggle"])
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_args[0][0][1:], ["record", "toggle"])

    def test_reload_dispatches_systemctl(self):
        with unittest.mock.patch.object(vox, "run_capture",
                                        return_value=Completed(0, "", "")) as m:
            rc = vox.main(["reload"])
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_args[0][0][0], "systemctl")


def _tmp():
    import tempfile
    return tempfile.TemporaryDirectory()


if __name__ == "__main__":
    unittest.main()
