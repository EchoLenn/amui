"""Offline regression checks. No live playback commands or lyrics requests."""
import argparse
import importlib.machinery
import importlib.util
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import sys
import io
import tempfile
import os

loader = importlib.machinery.SourceFileLoader("amui", str(Path(__file__).resolve().parents[1] / "bin/amui"))
spec = importlib.util.spec_from_loader(loader.name, loader)
amui = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = amui
loader.exec_module(amui)


class Screen:
    def __init__(self, h, w):
        self.h, self.w = h, w
        self.cells = {}

    def getmaxyx(self):
        return self.h, self.w

    def addstr(self, y, x, text, attr=0):
        assert 0 <= y < self.h and 0 <= x < self.w
        assert x + amui.width(text) < self.w
        for char in text:
            self.cells[y, x] = char, attr
            x += amui.width(char)

    def erase(self):
        self.cells.clear()

    clear = erase

    def refresh(self):
        pass


def make_ui(h=40, w=140):
    stop = threading.Event()
    player = amui.Player(stop)
    player.track = amui.Track(player="chromium.instance-test", identity="sample", title="Midnight Frequencies",
        artist="The Afterhours", album="A Room Full of Sound · 2026", length=245, position=97, status="Paused")
    lyrics = amui.Lyrics(stop)
    # Original fixture text, not third-party lyrics.
    lyrics.result = (player.track.lyrics_key(), [(0, "La ciudad baja la voz"), (30, "Y la noche enciende el color"),
        (95, "Todo suena un poco más cerca"), (115, "Cuando dejamos el ruido atrás"), (130, "Sólo queda esta canción")],
        [], "LRCLIB · sincronizadas")
    spectrum = amui.Spectrum(stop)
    spectrum.label = "CAVA · salida del sistema"
    spectrum.bars = [.15 + .75 * abs(amui.math.sin(i * .19)) for i in range(48)]
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
        config = amui.load_config()
    temporary = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(temporary.cleanup)
    ui = amui.UI(Screen(h, w), player, lyrics, spectrum,
                argparse.Namespace(theme="nocturne", no_lyrics=False, no_cava=False, config_data=config,
                                   config=str(Path(temporary.name)/"config.toml")))
    ui._test_directory = temporary
    ui.cover.enabled = False
    ui.palette = {i: i for i in range(1, 7)}
    return ui


class AmuiTests(unittest.TestCase):
    def test_duration_retained_only_for_same_track(self):
        raw = amui.SEP.join(["id", "Title", "Artist", "Album", "file:///cover", "245000000"])
        track = amui.metadata_track("chromium.instance1", raw, amui.Track())
        invalid = raw.replace("245000000", "9223372036854775807")
        self.assertEqual(amui.metadata_track(track.player, invalid, track).length, 245)
        self.assertEqual(amui.metadata_track(track.player, invalid.replace("Title", "Other"), track).length, 0)

    def test_empty_metadata_fields_keep_alignment(self):
        raw = amui.SEP.join(["", "Title", "Artist", "", "file:///cover", "1000000"])
        track = amui.metadata_track("test", raw, amui.Track())
        self.assertEqual((track.title, track.album, track.art, track.length), ("Title", "", "file:///cover", 1))

    def test_lrc_multiple_timestamps_and_offset(self):
        self.assertEqual(amui.parse_lrc("[offset:500]\n[00:10.20][01:02.50]Original test line"),
                         [(9.7, "Original test line"), (62., "Original test line")])

    def test_terminal_text_safety_and_width(self):
        self.assertNotIn("\x1b", amui.clean("\x1b[31mtrack\n"))
        for size in range(12):
            self.assertLessEqual(amui.width(amui.clip("歌曲 café é music", size)), size)

    def test_layouts_and_focus_fit(self):
        for h, w in [(8, 20), (22, 42), (24, 80), (35, 112), (40, 140), (60, 200)]:
            for help_ in (False, True):
                for focus in (False, True):
                    ui = make_ui(h, w)
                    ui.help, ui.focus = help_, focus
                    ui.render()
                    self.assertTrue(ui.screen.cells)

    def test_keyboard_routes_controls(self):
        ui = make_ui()
        for key, action in [(" ", "toggle"), ("m", "mute"), ("r", "restart"), ("l", "forward"),
                            (amui.curses.KEY_UP, "up")]:
            ui.key(key)
            self.assertEqual(ui.player.actions.get_nowait(), (ui.player.track.player, action))
        self.assertFalse(ui.key("q"))

    def test_mute_restores_and_volume_is_bounded(self):
        player = amui.Player(threading.Event())
        with patch.object(amui, "command", side_effect=["0.7", "0", "0.99", "0.01"]), \
             patch.object(amui.subprocess, "run") as run:
            run.return_value.returncode = 0
            for action, expected in [("mute", "0"), ("mute", "0.7"), ("up", "1"), ("down", "0")]:
                player.act("test", action)
                self.assertEqual(run.call_args.args[0][-1], expected)

    def test_no_lyrics_means_no_request(self):
        lyrics = amui.Lyrics(threading.Event(), enabled=False)
        lyrics.request(amui.Track(title="Track"))
        self.assertTrue(lyrics.requests.empty())

    def test_lyrics_retry_and_cache(self):
        lyrics = amui.Lyrics(threading.Event())
        track = amui.Track(title="Fixture", artist="Artist", album="Reissue", length=999)
        missing = amui.urllib.error.HTTPError("https://lrclib.net", 404, "Missing", {}, None)
        self.addCleanup(missing.close)
        payload = b'{"plainLyrics":"Original fixture line", "duration":200}'
        with tempfile.TemporaryDirectory() as directory:
            lyrics.cache = Path(directory)
            with patch.object(amui.urllib.request, "urlopen", side_effect=[missing, missing, io.BytesIO(payload)]) as fetch:
                result = lyrics.fetch(track, False)
                urls = [call.args[0].full_url for call in fetch.call_args_list]
                self.assertIn("album_name=Reissue", urls[0])
                self.assertNotIn("album_name", urls[1])
                self.assertNotIn("duration", urls[2])
                self.assertEqual(lyrics.fetch(track, False), result)
                self.assertEqual(fetch.call_count, 3)


if __name__ == "__main__":
    unittest.main()
