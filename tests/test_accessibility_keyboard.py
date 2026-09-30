"""Readable keyboard prompts and modal actions; no live playback or account writes."""
from unittest.mock import Mock
import unittest

from test_amui import amui, make_ui


def row_text(ui, row):
    return "".join(value[0] for (y, _), value in sorted(ui.screen.cells.items()) if y == row)


class AccessibilityKeyboardTests(unittest.TestCase):
    def test_help_is_modal_and_retains_page_close_and_quit_keys(self):
        ui = make_ui()
        ui.key("?")
        for key in (" ", "n", "H", "A", "Z", "/", amui.curses.KEY_UP, amui.curses.KEY_MOUSE):
            ui.key(key)
        self.assertTrue(ui.player.actions.empty())
        self.assertFalse(ui.sleep_menu)
        self.assertIsNone(ui.prompt)
        ui.key(amui.curses.KEY_NPAGE)
        self.assertEqual(ui.help_page, 1)
        ui.key("\x1b")
        self.assertFalse(ui.help)
        ui.key("?")
        self.assertFalse(ui.key("q"))
        ui.config["keybinds"]["help"] = ["LEFT"]
        ui.key(amui.curses.KEY_LEFT)
        self.assertFalse(ui.help)

    def test_theme_editor_labels_hex_editing_and_cancel_fit_compact_screen(self):
        ui = make_ui(8, 42)
        ui.key("T")
        ui.key("3")
        ui.key("\n")
        self.assertIsNotNone(ui.custom_edit)
        ui.theme_panel()
        self.assertIn("Fondo", row_text(ui, 0))
        self.assertIn("Esc", row_text(ui, 1))
        self.assertIn("#RRGGBB", row_text(ui, 2))
        ui.key("\x15")
        for key in "#abcdef":
            ui.key(key)
        ui.key(amui.curses.KEY_BACKSPACE)
        ui.key("0")
        self.assertEqual(ui.custom_hex, "#abcde0")
        ui.key("\n")
        self.assertEqual(ui.custom_step, 1)
        ui.key("\x1b")
        self.assertIsNone(ui.custom_edit)
        ui.key("\x1b")
        ui.key("\x1b")
        self.assertFalse(ui.theme_menu)
        self.assertFalse(ui.custom_path.exists())

    def test_music_prompts_keep_escape_visible_and_edit_unicode_by_keyboard(self):
        ui = make_ui(12, 45)
        ui.music = Mock(items=[], next_path="", label="Escribe una búsqueda", busy=False)
        ui.key("b")
        for key in "café":
            ui.key(key)
        ui.key(amui.curses.KEY_BACKSPACE)
        ui.key("é")
        self.assertEqual(ui.music_query, "café")
        ui.music_panel()
        self.assertIn("Esc salir", row_text(ui, 8))
        self.assertIn("Ctrl+U", row_text(ui, 9))
        ui.key("\x15")
        self.assertEqual(ui.music_query, "")
        for key in "Song":
            ui.key(key)
        ui.key("\n")
        ui.music.search.assert_called_once_with("Song", False, "songs", "")
        ui.key("\x1b")
        self.assertFalse(ui.music_open)

    def test_small_queue_confirmation_exposes_question_and_cancel(self):
        ui = make_ui(24, 42)
        view = (ui.player.track.identity, ((4, "Song", "Artist"),), ("queue",))
        ui.extras = Mock(identity=ui.player.track.identity, items=[("Song", "Artist")],
                         label="Cider API", queue_view=view, shuffle=False, repeat="None")
        ui.key("Q")
        ui.render()
        ui.key("d")
        ui.render()
        self.assertIn("¿Borrar canción?", row_text(ui, 3))
        self.assertIn("Esc cancela", row_text(ui, 14))
        ui.key("\x1b")
        self.assertIsNone(ui.queue_confirm)
        self.assertTrue(ui.player.actions.empty())
        ui.key("c")
        ui.key("\n")
        _, action = ui.player.actions.get_nowait()
        self.assertEqual(action, ("queue", 0, view, "clear_pending"))

    def test_favorite_status_and_shortcut_have_readable_labels(self):
        ui = make_ui()
        ui.extras = Mock(library_identity=ui.player.track.identity, favorite=True, library=False,
                         shuffle=False, repeat="None")
        ui.now_playing(3, 2, 20, 78, ui.player.track)
        self.assertIn("FAVORITO", row_text(ui, 20))
        ui.transport(30, 140, ui.player.track)
        self.assertIn("H favorito", row_text(ui, 35))

    def test_empty_form_explains_requirement_and_can_be_cancelled(self):
        ui = make_ui()
        ui.key("/")
        ui.key("\x15")
        ui.key("\n")
        self.assertEqual(ui.prompt, "title")
        self.assertIn("Escribe un valor", ui.toast_text)
        ui.key("\x1b")
        self.assertIsNone(ui.prompt)
        ui.lyrics.request = Mock()
        ui.key("/")
        ui.key("\x15")
        for key in "Título":
            ui.key(key)
        ui.key("\n")
        self.assertEqual(ui.prompt, "artist")
        ui.key("\x15")
        for key in "Artista":
            ui.key(key)
        ui.key("\n")
        self.assertIsNone(ui.prompt)
        ui.lyrics.request.assert_called_once_with(ui.player.track, retry=True, query=("Título", "Artista"))


if __name__ == "__main__":
    unittest.main()
