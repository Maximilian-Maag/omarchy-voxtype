"""Regression tests — pin the contracts this plugin must not silently break.

These are static/structural checks on the shipped files (the things a refactor most
easily breaks without any functional test going red).
"""

import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "bin/omarchy-voxtype"
HOOK = ROOT / "hooks/voxtype-theme-set"
BINDINGS = ROOT / "bin/bindings.lua"


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.mf = json.loads((ROOT / "manifest.json").read_text())

    def test_id_is_owner_dot_name(self):
        self.assertEqual(self.mf["id"], "Maximilian-Maag.voxtype")

    def test_id_is_not_reserved_namespace(self):
        self.assertFalse(self.mf["id"].startswith("omarchy."))

    def test_version_matches_newest_changelog_heading(self):
        text = (ROOT / "CHANGELOG.md").read_text()
        versions = re.findall(r"^##\s*\[?v?([0-9]+\.[0-9]+\.[0-9]+)", text, re.M)
        self.assertTrue(versions, "no CHANGELOG version heading found")
        self.assertEqual(self.mf["version"], versions[0])

    def test_entry_points_is_object(self):
        self.assertIsInstance(self.mf["entryPoints"], dict)

    def test_schema_version_is_number(self):
        self.assertIsInstance(self.mf["schemaVersion"], int)


class TestHookFilenameHazard(unittest.TestCase):
    """`omarchy hook install` names by BASENAME, so a generic name clobbers peers."""

    def test_hook_file_is_uniquely_named(self):
        self.assertTrue(HOOK.is_file(), "expected hooks/voxtype-theme-set")
        self.assertNotEqual(HOOK.name, "theme-set")

    def test_generic_named_hook_is_not_shipped(self):
        self.assertFalse((ROOT / "hooks/theme-set").exists(),
                         "a bare hooks/theme-set would clobber other plugins' hooks")

    def test_hook_self_locates_instead_of_bash_source_parent(self):
        text = HOOK.read_text()
        # $(dirname "$BASH_SOURCE")/.. resolves to the hooks dir once installed.
        self.assertNotIn('dirname "${BASH_SOURCE[0]}")/..', text)
        # Instead it searches known plugin locations.
        self.assertIn("omarchy/plugins/Maximilian-Maag.voxtype", text)
        self.assertIn("OMARCHY_VOXTYPE_DIR", text)

    def test_install_script_installs_the_unique_hook(self):
        text = (ROOT / "install.sh").read_text()
        self.assertIn("hooks/voxtype-theme-set", text)
        self.assertIn("omarchy hook install theme-set", text)


class TestNoBakedPalette(unittest.TestCase):
    """Colours must be read from the applied theme at runtime, never baked in."""

    def test_cli_has_no_hex_colour_literals(self):
        text = CLI.read_text()
        literals = re.findall(r"#[0-9A-Fa-f]{6}\b", text)
        self.assertEqual(literals, [], "hardcoded colour literal(s): %s" % literals)

    def test_hook_has_no_hex_colour_literals(self):
        text = HOOK.read_text()
        self.assertEqual(re.findall(r"#[0-9A-Fa-f]{6}\b", text), [])

    def test_cli_reads_the_applied_theme_path(self):
        self.assertIn("omarchy/current/theme/colors.toml", CLI.read_text())

    def test_cli_never_defaults_to_a_named_theme(self):
        text = CLI.read_text()
        for name in ("catppuccin", "gruvbox", "tokyo-night", "nord"):
            self.assertNotIn(name, text.lower())


class TestControlInterface(unittest.TestCase):
    """The CLI must drive voxtype's REAL interface, not invent one."""

    def test_uses_the_record_subcommand(self):
        text = CLI.read_text()
        for action in ("toggle", "start", "stop", "cancel"):
            self.assertIn('"%s"' % action, text)
        self.assertIn('"record"', text)

    def test_does_not_reimplement_recording(self):
        text = CLI.read_text()
        self.assertNotIn("SIGUSR1", text)
        self.assertNotIn("SIGUSR2", text)
        self.assertNotIn("parecord", text)


class TestBindingsModule(unittest.TestCase):
    def test_bindings_file_exists_and_is_lua(self):
        self.assertTrue(BINDINGS.is_file())

    def test_bindings_cover_toggle_cancel_status(self):
        text = BINDINGS.read_text()
        self.assertIn("voxtype record toggle", text)
        self.assertIn("voxtype record cancel", text)
        self.assertIn("omarchy-voxtype status", text)

    def test_bindings_unbind_before_bind(self):
        text = BINDINGS.read_text()
        self.assertEqual(text.count("hl.unbind("), text.count("o.bind("))

    def test_install_script_wires_bindings_into_hyprland(self):
        self.assertIn('require("hypr.voxtype-bindings")', (ROOT / "install.sh").read_text())


class TestPolicyDeclaresEveryKind(unittest.TestCase):
    def test_kinds(self):
        cfg = json.loads((ROOT / "policy.json").read_text())
        self.assertEqual(set(cfg["tests"]["kinds"]),
                         {"unit", "regression", "integration", "e2e", "shell"})

    def test_min_kill_rate_floor(self):
        cfg = json.loads((ROOT / "policy.json").read_text())
        self.assertGreaterEqual(cfg["tests"]["min_kill_rate"], 0.8)


class TestConfigShape(unittest.TestCase):
    def test_config_declares_bindings(self):
        cfg = json.loads((ROOT / "config/voxtype.json").read_text())
        self.assertIn("bindings", cfg)
        self.assertIn("toggle", cfg["bindings"])

    def test_default_keys_match_the_cli(self):
        cfg = json.loads((ROOT / "config/voxtype.json").read_text())
        text = CLI.read_text()
        for key, value in cfg["bindings"].items():
            self.assertIn(value, text, "config key %s not present in CLI defaults" % key)


if __name__ == "__main__":
    unittest.main()
