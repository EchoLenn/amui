"""Rendered xterm color roles, rather than unquantized theme hex values."""
from contextlib import ExitStack
import unittest
from unittest.mock import patch

from test_amui import amui, make_ui
import features as f


class AccessibilityContrastTests(unittest.TestCase):
    def color_context(self, count=256):
        stack = ExitStack()
        stack.enter_context(patch.object(amui.curses, "has_colors", return_value=True))
        stack.enter_context(patch.object(amui.curses, "COLORS", count, create=True))
        stack.enter_context(patch.object(amui.curses, "start_color"))
        stack.enter_context(patch.object(amui.curses, "color_pair", side_effect=lambda pair: pair << 8))
        pairs = {}
        stack.enter_context(patch.object(amui.curses, "init_pair", side_effect=lambda pair, fg, bg: pairs.update({pair: (fg, bg)})))
        return stack, pairs

    def assert_readable_roles(self, pairs):
        self.assertTrue(all(role in pairs for role in range(1, 7)))
        for role, (fg, bg) in pairs.items():
            self.assertGreaterEqual(f.contrast(f.rgb(fg), f.rgb(bg)), 3 if role == 3 else 4.5,
                                    f"Role {role}, foreground {fg}, background {bg}")

    def test_all_fixed_themes_render_readable_secondary_selected_and_border_roles(self):
        ui = make_ui()
        for name, palette in amui.THEMES.items():
            with self.subTest(theme=name):
                ui.theme = name
                context, pairs = self.color_context()
                with context, patch.object(ui.screen, "bkgd", create=True):
                    ui.colors()
                    self.assert_readable_roles(pairs)
                    for row, role in enumerate((1, 2, 4, 5, 6)):
                        ui.text(row, 0, "Canción seleccionada" if role == 4 else "Artista y álbum", role,
                                bold=role == 4)
                self.assertEqual(ui.themes[name], palette)
                for role, (fg, bg) in pairs.items():
                    original = palette[role]
                    if f.contrast(f.rgb(original), f.rgb(palette[0])) >= (3 if role == 3 else 4.5):
                        self.assertEqual(fg, original, "Already readable theme colors should stay unchanged")

    def test_custom_and_dynamic_palettes_are_corrected_only_when_rendered(self):
        ui = make_ui()
        for background in (16, 234, 244, 255):
            raw = (background,) * 7
            for source in ("custom", "cover"):
                with self.subTest(background=background, source=source):
                    ui.dynamic_colors = raw if source == "cover" else None
                    ui.themes["custom"] = raw
                    ui.theme = "custom"
                    context, pairs = self.color_context()
                    with context, patch.object(ui.screen, "bkgd", create=True):
                        ui.colors()
                    self.assert_readable_roles(pairs)
                    self.assertTrue(all(bg == background for _, bg in pairs.values()))
                    self.assertEqual(ui.themes["custom"], raw)
                    self.assertEqual(ui.dynamic_colors, raw if source == "cover" else None)

    def test_fade_never_hides_metadata_even_on_first_frame_or_light_custom_theme(self):
        ui = make_ui()
        palettes = [*amui.THEMES.values(), (255, 255, 254, 253, 252, 251, 250)]
        for palette in palettes:
            for elapsed in (0, .01, .325, .65, 1):
                with self.subTest(palette=palette, elapsed=elapsed):
                    ui.dynamic_colors, ui.changed_at, ui.fade_done = palette, 100, None
                    context, pairs = self.color_context()
                    with context, patch.object(amui.time, "monotonic", return_value=100+elapsed):
                        ui.fade()
                    self.assertEqual(set(pairs), {7, 8, 9})
                    for fg, bg in pairs.values():
                        self.assertGreaterEqual(f.contrast(f.rgb(fg), f.rgb(bg)), 4.5)

    def test_eight_color_fallback_uses_readable_text_and_no_dim_attribute(self):
        ui = make_ui()
        context, pairs = self.color_context(8)
        with context, patch.object(ui.screen, "bkgd", create=True), patch.object(ui.screen, "addstr") as write:
            ui.colors()
            self.assert_readable_roles(pairs)
            ui.text(0, 0, "Información secundaria", 2)
            ui.text(1, 0, "› Selección", 4, True)
        self.assertEqual([call.args[3] & amui.curses.A_DIM for call in write.call_args_list], [0, 0])


if __name__ == "__main__":
    unittest.main()
