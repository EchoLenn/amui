"""Check concrete audit regressions without live playback or graphics."""
from dataclasses import replace
import io
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from test_amui import amui, make_ui


class AuditRegressionTests(unittest.TestCase):
    def test_queued_controls_are_dropped_after_player_changes_or_disconnects(self):
        actions = ("next", "previous", "toggle", "pause", "up", "down", "mute",
                   "shuffle", "repeat", "forward", "back", "restart",
                   ("seek", 20, "old-track"), ("queue", 0, ("old-track", (), ())),
                   ("library", "favorite", "old-track"))
        player = amui.Player(threading.Event())
        player.extras = Mock(api_available=True)
        with patch.object(amui, "command", side_effect=AssertionError("Stale MPRIS query")), \
             patch.object(amui.subprocess, "run", side_effect=AssertionError("Stale playback command")):
            for destination in ("chromium.instance2", ""):
                for action in actions:
                    with self.subTest(destination=destination, action=action):
                        player.track = amui.Track(player="chromium.instance1", identity="old-track")
                        player.send(action)
                        captured = player.actions.get_nowait()
                        player.track = replace(player.track, player=destination, identity="new-track")
                        player.act(*captured)
                        self.assertIn("reproductor cambió", player.notice)
        self.assertEqual(player.extras.mock_calls, [])

    def test_failed_kitty_draw_is_throttled_but_retries_and_new_art_draws_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            art = Path(directory) / "cover.ppm"
            art.write_bytes(b"P6\n1 1\n255\n\x00\x00\x00")
            new_art = Path(directory) / "new.ppm"
            new_art.write_bytes(b"P6\n1 1\n255\n\xff\xff\xff")
            for failure in (Mock(returncode=1), subprocess.TimeoutExpired("icat", 2)):
                with self.subTest(failure=type(failure).__name__):
                    cover = amui.Cover("kitty")
                    cover.enabled, cover.command = True, ["kitten", "icat"]
                    now = [100.]
                    effects = [failure, Mock(returncode=0), Mock(returncode=0)]
                    with patch.object(amui.time, "monotonic", side_effect=lambda: now[0]), \
                         patch.object(amui.subprocess, "run", side_effect=effects) as draw, \
                         patch.object(amui.sys, "stdout", new_callable=io.StringIO) as output:
                        cover.show(str(art), (4, 5, 26, 13))
                        for frame in range(20):
                            now[0] = 100 + frame / 30
                            cover.show(str(art), (4, 5, 26, 13))
                        self.assertEqual(draw.call_count, 1, "A failed encoder must not run every frame")
                        self.assertEqual(output.getvalue(), "\x1b7\x1b8", "Restore cursor after failure")
                        now[0] = 111
                        cover.show(str(art), (4, 5, 26, 13))
                        self.assertEqual(draw.call_count, 2)
                        self.assertTrue(cover.drawn)
                        cover.show(str(art), (4, 5, 26, 13))
                        self.assertEqual(draw.call_count, 2, "Successful static artwork needs no redraw")
                    # A new track/image is eligible immediately even after failure.
                    cover = amui.Cover("kitty")
                    cover.enabled, cover.command = True, ["kitten", "icat"]
                    with patch.object(amui.time, "monotonic", return_value=100), \
                         patch.object(amui.subprocess, "run", side_effect=[failure, Mock(returncode=0)]) as draw, \
                         patch.object(amui.sys, "stdout", new_callable=io.StringIO):
                        cover.show(str(art), (4, 5, 26, 13))
                        cover.show(str(new_art), (4, 5, 26, 13))
                        self.assertEqual(draw.call_count, 2)
                        self.assertTrue(cover.drawn)

    def test_completed_fade_keeps_color_roles_without_per_frame_recalculation(self):
        ui = make_ui()
        ui.changed_at = 100
        with patch.object(amui.time, "monotonic", return_value=102), \
             patch.object(amui.curses, "has_colors", return_value=True), \
             patch.object(amui.curses, "COLORS", 256, create=True), \
             patch.object(amui.curses, "init_pair") as colors, \
             patch.object(amui.curses, "color_pair", side_effect=lambda pair: pair), \
             patch.object(amui, "nearest_color", side_effect=AssertionError("Completed fade recalculated RGB")):
            ui.fade()
            self.assertEqual(colors.call_count, 3)
            self.assertTrue(all(role in ui.palette for role in (7, 8, 9)))
            for _ in range(20):
                ui.fade()
            self.assertEqual(colors.call_count, 3)
            ui.theme = "ember"
            ui.fade()
            self.assertEqual(colors.call_count, 6, "A changed palette must update text colors")
            for _ in range(20):
                ui.fade()
            self.assertEqual(colors.call_count, 6)


if __name__ == "__main__":
    unittest.main()
