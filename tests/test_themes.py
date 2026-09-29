"""Theme interaction, reload and image palette regressions."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_amui import amui, make_ui
import features as f


class ThemeTests(unittest.TestCase):
    def test_picker_preview_cancel_and_accept(self):
        ui = make_ui()
        original = ui.theme
        ui.config['dynamic_palette'] = True
        ui.key('T')
        ui.key(amui.curses.KEY_DOWN)
        self.assertNotEqual(ui.theme, original)
        ui.key('\x1b')
        self.assertEqual(ui.theme, original)
        self.assertTrue(ui.config['dynamic_palette'])
        ui.key('T')
        ui.key(amui.curses.KEY_DOWN)
        ui.key('\n')
        self.assertFalse(ui.theme_menu)
        self.assertFalse(ui.config['dynamic_palette'])
        self.assertNotEqual(ui.theme, original)

    def test_picker_fits_small_and_large_terminals(self):
        with patch.object(amui.curses, 'has_colors', return_value=False):
            for h, w in [(2, 25), (8, 32), (20, 65), (40, 140)]:
                ui = make_ui(h, w)
                ui.key('T')
                ui.theme_panel()
                self.assertTrue(ui.screen.cells)

    def test_reload_keeps_last_valid_theme(self):
        with tempfile.TemporaryDirectory() as directory:
            ui = make_ui()
            ui.config_path = Path(directory) / 'config.toml'
            ui.config_path.write_text('[themes.custom]\n' + '\n'.join(f'{k} = 120' for k in f.COLOR_NAMES))
            ui.reload_themes()
            self.assertIn('custom', ui.themes)
            ui.config_path.write_text('theme = [invalid')
            ui.config_check_at = 0
            ui.reload_themes()
            self.assertIn('custom', ui.themes)
            self.assertIn('sin cambios', ui.toast_text)

    def test_transition_finishes_and_respects_disabled_animation(self):
        ui = make_ui()
        target = ui.themes['ocean']
        with patch.object(ui, 'colors'):
            ui.transition_to(target)
            ui.color_started -= 2
            ui.animate_colors()
            self.assertEqual(ui.dynamic_colors, target)
            ui.config['animations'] = False
            ui.transition_to(ui.themes['forest'])
            ui.animate_colors()
            self.assertEqual(ui.dynamic_colors, ui.themes['forest'])

    def test_palette_cache_content_invalidation_and_contrast(self):
        if not f.shutil.which('magick'):
            self.skipTest('ImageMagick optional')
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CACHE_HOME': directory}):
            image = Path(directory) / 'cover.ppm'
            image.write_bytes(b'P6\n2 2\n255\n' + bytes([20, 80, 220])*4)
            fallback = amui.THEMES['nocturne']
            first = f.dominant_palette(str(image), fallback)
            with patch.object(f.subprocess, 'run', side_effect=AssertionError('Cache missed')):
                self.assertEqual(first, f.dominant_palette(str(image), fallback))
            image.write_bytes(b'P6\n2 2\n255\n' + bytes([250, 220, 180])*4)
            second = f.dominant_palette(str(image), fallback, light=True)
            self.assertNotEqual(first, second)
            for palette in (first, second):
                for i in (1, 2, 4, 5, 6):
                    self.assertGreaterEqual(f.contrast(f.rgb(palette[0]), f.rgb(palette[i])), 4.5)

    def test_clusters_preserve_distinct_colors(self):
        pixels = [(255, 0, 0)]*8 + [(0, 0, 255)]*4 + [(0, 255, 0)]*2
        self.assertEqual(f.cluster_colors(pixels), [(255, 0, 0), (0, 0, 255), (0, 255, 0)])

    def test_list_themes_without_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([str(Path(amui.__file__).resolve()), '--list-themes'],
                                    env={**os.environ, 'XDG_CONFIG_HOME': directory}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('sakura', result.stdout)
            self.assertIn('forest', result.stdout)
            self.assertNotIn('\x1b', result.stdout)
