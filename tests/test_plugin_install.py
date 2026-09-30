"""Headless plugin installer acceptance; never touch a live Cider profile."""
from contextlib import ExitStack
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_amui import amui


class PluginInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.config_home = self.directory / "config"
        self.environment = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.config_home)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.source = Path(__file__).resolve().parents[1] / "share/amui/cider-plugin"

    def invoke(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(amui.sys, "argv", ["amui", "--install-cider-plugin", *args]))
            stack.enter_context(patch.object(amui.sys, "stdout", output))
            stack.enter_context(patch.object(amui.sys, "stderr", errors))
            stack.enter_context(patch.object(amui, "load_config", side_effect=AssertionError("Loaded music configuration")))
            stack.enter_context(patch.object(amui, "command", side_effect=AssertionError("Queried a live player")))
            stack.enter_context(patch.object(amui.subprocess, "run", side_effect=AssertionError("Started a process")))
            stack.enter_context(patch.object(amui.subprocess, "Popen", side_effect=AssertionError("Started a process")))
            stack.enter_context(patch.object(amui.threading.Thread, "start", side_effect=AssertionError("Started a worker")))
            stack.enter_context(patch.object(amui.curses, "wrapper", side_effect=AssertionError("Opened curses")))
            for name in ("Player", "Lyrics", "Spectrum", "Extras", "Activity", "MusicBrowser", "UI"):
                stack.enter_context(patch.object(amui, name, side_effect=AssertionError("Created " + name)))
            try:
                code = amui.main()
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def assert_installed(self, target):
        for name in ("plugin.js", "plugin.yml"):
            self.assertEqual((target / name).read_bytes(), (self.source / name).read_bytes())

    def test_explicit_directory_copies_only_two_plugin_files_without_music_services(self):
        target = self.directory / "custom profile" / "amui"
        code, output, errors = self.invoke(str(target))
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("Complemento instalado:", output)
        self.assertIn(str(target), output)
        self.assertIn("Settings", output)
        self.assertIn("Plugins", output)
        self.assertIn("activa amui Favorites Bridge", output)
        self.assert_installed(target)
        self.assertEqual({path.name for path in target.iterdir()}, {"plugin.js", "plugin.yml"})
        self.assertFalse(self.config_home.exists())

    def test_changed_originals_are_backed_up_and_identical_reinstall_preserves_backup(self):
        target = self.directory / "existing"
        target.mkdir()
        old = {"plugin.js": b"original customized JS", "plugin.yml": b"original customized YAML"}
        for name, contents in old.items():
            (target / name).write_bytes(contents)
        self.assertEqual(self.invoke(str(target))[0], 0)
        self.assert_installed(target)
        for name, contents in old.items():
            self.assertEqual((target / (name + ".previous")).read_bytes(), contents)
        self.assertEqual(self.invoke(str(target))[0], 0)
        for name, contents in old.items():
            self.assertEqual((target / (name + ".previous")).read_bytes(), contents)

    def test_identical_reinstall_creates_no_backups(self):
        target = self.directory / "same"
        self.assertEqual(self.invoke(str(target))[0], 0)
        self.assertEqual(self.invoke(str(target))[0], 0)
        self.assertEqual({path.name for path in target.iterdir()}, {"plugin.js", "plugin.yml"})

    def test_default_requires_existing_cider_profile_without_creating_random_directories(self):
        code, output, errors = self.invoke()
        self.assertEqual((code, output), (1, ""))
        self.assertIn("No se encontró Cider", errors)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_default_uses_xdg_cider_profile_and_plugin_identifier(self):
        cider_home = self.config_home / "sh.cider.genten"
        cider_home.mkdir(parents=True)
        code, output, errors = self.invoke()
        target = cider_home / "plugins/io.github.echolenn.amui"
        self.assertEqual((code, errors), (0, ""))
        self.assertIn(str(target), output)
        self.assert_installed(target)
        self.assertEqual({path.name for path in cider_home.iterdir()}, {"plugins"})

    def test_existing_file_as_target_reports_error_and_preserves_it(self):
        target = self.directory / "not-a-directory"
        target.write_text("preserve this file")
        code, output, errors = self.invoke(str(target))
        self.assertEqual((code, output), (1, ""))
        self.assertIn("amui:", errors)
        self.assertEqual(target.read_text(), "preserve this file")


if __name__ == "__main__":
    unittest.main()
