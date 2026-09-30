"""Acceptance checks for integrated features; no external account writes."""
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock

from test_amui import amui, make_ui
import features as f


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.tmp.name, "XDG_CACHE_HOME": self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def config_file(self, text):
        path = Path(self.tmp.name) / "test.toml"
        path.write_text(text)
        return path

    def test_config_custom_theme_keybindings_and_defaults(self):
        text = (Path(__file__).resolve().parents[1] / "share/amui/config.example.toml").read_text()
        config = f.load_config(self.config_file(text.replace('shuffle = "s"', 'shuffle = "z"')))
        self.assertEqual(config["keymap"]["z"], "shuffle")
        self.assertNotIn("s", config["keymap"])
        self.assertEqual(len(config["themes"]["aurora"]), 7)
        self.assertTrue(config["dynamic_palette"])
        self.assertEqual(config["scrobble"]["providers"], [])

    def test_config_rejects_bad_types_collisions_and_remote_token_destinations(self):
        for text in ['cava = "yes"', 'lyrics_offset = nan', 'cover_protocol="bad"',
                     '[keybinds]\nshuffle="q"', '[keybinds]\nbogus="x"',
                     '[cider]\nurl="https://example.com"', '[scrobble]\nproviders=["fake"]']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                f.load_config(self.config_file(text))

    def test_cider_connect_verifies_then_saves_private_token(self):
        config = f.load_config()
        path = Path(self.tmp.name) / "cider.token"
        config["cider"]["token_file"] = str(path)
        with patch.object(f.getpass, "getpass", return_value="fixture-token"), \
             patch.object(f, "json_request", return_value={"status": "ok"}) as request, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            f.connect_cider(config)
        self.assertEqual(path.read_text(), "fixture-token")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("fixture-token", output.getvalue())
        self.assertTrue(request.call_args.args[0].endswith("/playback/active"))

    def test_mpris_queue_excludes_playing_and_history(self):
        stop = threading.Event()
        track = amui.Track(player="fixture", identity="id", title="Current")
        extras = f.Extras(stop, Mock(track=track), f.load_config())
        def bus(player, method, interface, member, *args):
            return {"Shuffle": True, "LoopStatus": "Track", "Tracks": ["/a", "/b", "/c"],
                    "Metadata": {"mpris:trackid": "/b"},
                    "GetTracksMetadata": [[{"xesam:title": "Next", "xesam:artist": ["One", "Two"]}]]}[member]
        with patch.object(f, "bus", side_effect=bus):
            extras.poll(track)
        self.assertEqual(extras.items, [("Next", "One, Two")])
        self.assertEqual((extras.shuffle, extras.repeat), (True, "Track"))

    def test_cider_queue_handles_duplicates_honestly(self):
        def item(id, title):
            return {"id": id, "attributes": {"name": title, "artistName": "Artist"}}
        data = [item("1", "Old"), item("2", "Now"), item("3", "Next")]
        current = {"playParams": {"id": "2"}, "name": "Now"}
        self.assertEqual(f.cider_queue(data, current)[0], [("Next", "Artist")])
        duplicate = data + [item("2", "Now")]
        self.assertEqual(f.cider_queue(duplicate, current)[0], [])
        self.assertEqual(f.cider_queue({"items": duplicate, "position": 1}, current)[0],
                         [("Next", "Artist"), ("Now", "Artist")])

    def test_shuffle_repeat_commands_and_ui_binding(self):
        player = amui.Player(threading.Event())
        player.track = amui.Track(player="fixture")
        with patch.object(amui, "command", side_effect=["Off", "None", "Playlist", "Track"]), \
             patch.object(amui.subprocess, "run") as run:
            run.return_value.returncode = 0
            for action, tail in [("shuffle", ["shuffle", "On"]), ("repeat", ["loop", "Playlist"]),
                                 ("repeat", ["loop", "Track"]), ("repeat", ["loop", "None"])]:
                player.act("fixture", action)
                self.assertEqual(run.call_args.args[0][-2:], tail)
        ui = make_ui()
        ui.config["keymap"]["z"] = ui.config["keymap"].pop("s")
        ui.key("z")
        self.assertEqual(ui.player.actions.get()[1], "shuffle")

    def test_history_recent_corrupt_lines_and_unicode(self):
        history = f.History(Path(self.tmp.name) / "history.jsonl")
        track = amui.Track(title="Canción", artist="Artista", album="Álbum")
        history.append(track, 1000)
        with history.path.open("a") as file:
            file.write('broken\n{"title":"incomplete"}\n')
        history.append(replace(track, title="Next"), 1001)
        self.assertEqual([row["title"] for row in history.recent(2)], ["Next", "Canción"])
        self.assertTrue(history.recent(1)[0]["timestamp"].endswith("+00:00"))

    def test_prompt_does_not_dispatch_playback_keys(self):
        ui = make_ui()
        ui.key("/")
        ui.key("\x15")
        for key in "Quiet Night":
            ui.key(key)
        ui.key("\n")
        ui.key("\x15")
        for key in "Artist":
            ui.key(key)
        ui.key("\n")
        self.assertIsNone(ui.prompt)
        self.assertTrue(ui.player.actions.empty())
        request = ui.lyrics.requests.get_nowait()
        self.assertEqual(request[2], ("Quiet Night", "Artist"))
        ui.lyrics.request(ui.player.track)
        self.assertTrue(ui.lyrics.requests.empty(), "auto lookup must not replace manual query")

    def test_export_preserves_timestamps_and_never_overwrites(self):
        track = amui.Track(title="../../title", artist="../artist")
        path = f.export_lyrics(track, [(1.23, "Original line"), (62.5, "Next line")], [], self.tmp.name)
        self.assertEqual(path.parent, Path(self.tmp.name))
        self.assertEqual(amui.parse_lrc(path.read_text()), [(1.23, "Original line"), (62.5, "Next line")])
        other = f.export_lyrics(track, [(1.23, "Original line")], [], self.tmp.name)
        self.assertNotEqual(path, other)
        plain = f.export_lyrics(track, [], ["Plain fixture"], self.tmp.name)
        self.assertEqual(plain.suffix, ".txt")

    def test_export_prompt_retains_track_snapshot(self):
        ui = make_ui()
        original = ui.player.track
        ui.key("S")
        ui.player.track = replace(original, title="Changed song")
        ui.prompt_value = self.tmp.name
        ui.key("\n")
        path = next(Path(self.tmp.name).glob("*.lrc"))
        self.assertIn(original.title, path.name)
        self.assertNotIn("Changed song", path.name)

    def test_mouse_seek_and_lyrics_scroll(self):
        ui = make_ui()
        ui.render()
        x, y, size = ui.progress_rect
        with patch.object(amui.curses, "getmouse", return_value=(0, x + size - 1, y, 0, amui.curses.BUTTON1_CLICKED)):
            ui.mouse()
        action = ui.player.actions.get()[1]
        self.assertEqual(action, ("seek", ui.player.track.length, ui.player.track.identity))
        x, y, _, _ = ui.lyrics_rect
        with patch.object(amui.curses, "getmouse", return_value=(0, x + 1, y + 1, 0, amui.curses.BUTTON4_PRESSED)):
            ui.mouse()
        self.assertEqual(ui.scroll, -3)

    def test_seek_for_previous_song_is_dropped(self):
        player = amui.Player(threading.Event())
        player.track = amui.Track(identity="current", length=120)
        with patch.object(amui.subprocess, "run") as run:
            player.act("fixture", ("seek", 50, "previous"))
        run.assert_not_called()

    def test_mini_uses_only_two_rows_and_toast_expires(self):
        ui = make_ui(2, 100)
        ui.options.mini = True
        with patch.object(amui.time, "monotonic", return_value=10):
            ui.toast("Song changed")
            ui.render()
        self.assertTrue(all(y in (0, 1) for y, _ in ui.screen.cells))
        self.assertEqual(ui.toast_until, 13)
        with patch.object(amui.time, "monotonic", return_value=14):
            ui.render()
        text = "".join(char for char, _ in ui.screen.cells.values())
        self.assertNotIn("Song changed", text)

    def test_cover_detection_and_iterm_packet(self):
        for env, expected in [({"TERM": "xterm-kitty"}, "kitty"), ({"TERM_PROGRAM": "WezTerm"}, "iterm"),
                              ({"TERM_PROGRAM": "iTerm.app"}, "iterm"), ({"TERM": "foot"}, "sixel"), ({}, "none")]:
            self.assertEqual(f.detect_cover(environ=env), expected)
        image = Path(self.tmp.name) / "image.png"
        image.write_bytes(b"fixture image")
        payload = f.inline_image(str(image), (2, 3, 20, 10), "iterm")
        self.assertTrue(payload.startswith(b"\x1b]1337;File=inline=1"))
        self.assertIn(b"width=20;height=10", payload)
        self.assertTrue(payload.endswith(b"\a"))

    def test_real_dynamic_palette_and_sixel_encoder(self):
        if not f.shutil.which("magick"):
            self.skipTest("Optional ImageMagick not installed")
        # PPM fixture doesn't need a Python imaging library.
        image = Path(self.tmp.name) / "cover.ppm"
        image.write_bytes(b"P6\n2 2\n255\n" + bytes([20, 80, 220]) * 4)
        palette = f.dominant_palette(str(image), amui.THEMES["nocturne"])
        self.assertNotEqual(palette[4:], amui.THEMES["nocturne"][4:])
        data = f.inline_image(str(image), (0, 0, 10, 5), "sixel")
        self.assertIn(b"\x1bP", data)
        self.assertIn(b"\x1b\\", data)

    def test_smooth_progress_converges_without_overshoot(self):
        value = 0
        values = []
        for _ in range(30):
            value = f.smooth(value, .8, 1 / 30)
            values.append(value)
        self.assertTrue(all(a <= b <= .8 for a, b in zip(values, values[1:])))
        self.assertAlmostEqual(value, .8, places=5)

    def test_fade_stays_readable_and_reaches_foreground(self):
        ui = make_ui()
        ui.changed_at = 0
        results = []
        with patch.object(amui.curses, "has_colors", return_value=True), \
             patch.object(amui.curses, "COLORS", 256, create=True), \
             patch.object(amui.curses, "color_pair", side_effect=lambda n: n), \
             patch.object(amui.curses, "init_pair") as initialize:
            for now in (0, .325, .65):
                with patch.object(amui.time, "monotonic", return_value=now):
                    ui.fade()
                results.append(initialize.call_args_list[-3].args[1])
        background = amui.THEMES["nocturne"][0]
        for color in results:
            self.assertGreaterEqual(f.contrast(f.rgb(color), f.rgb(background)), 4.5)
        self.assertEqual(results[-1], amui.THEMES["nocturne"][1])
        self.assertNotIn(results[1], (results[0], results[-1]))

    def test_manual_lyrics_worker_discards_late_results(self):
        stop, entered, release = threading.Event(), threading.Event(), threading.Event()
        lyrics = amui.Lyrics(stop)
        track = amui.Track(title="Current", artist="Artist", length=100)
        def fetch(query, retry):
            if query.title == "Old query":
                entered.set()
                release.wait(2)
            return {"plainLyrics": query.title, "duration": 100}
        with patch.object(lyrics, "fetch", side_effect=fetch):
            lyrics.thread.start()
            try:
                lyrics.request(track, query=("Old query", "Artist"))
                self.assertTrue(entered.wait(1))
                lyrics.request(track, retry=True, query=("New query", "Artist"))
                release.set()
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and lyrics.result[2] != ["New query"]:
                    stop.wait(.01)
                self.assertEqual(lyrics.result[2], ["New query"])
            finally:
                release.set()
                stop.set()
                lyrics.thread.join(2)

    def test_scrobble_threshold_ignores_pause_and_seek(self):
        activity = f.Activity(threading.Event(), Mock(), f.load_config(), amui.THEMES["nocturne"])
        activity.history.append = Mock()
        activity.scrobbler.enqueue = Mock()
        track = amui.Track(identity="song", title="Title", artist="Artist", length=120, status="Playing")
        for sec in range(50):
            activity.observe(replace(track, position=sec), sec, 1000 + sec)
        activity.observe(replace(track, status="Paused", position=49), 50, 1050)
        activity.observe(replace(track, status="Paused", position=49), 80, 1080)
        activity.observe(replace(track, position=110), 81, 1081)  # seek isn't listening
        self.assertEqual(activity.listened, 49)
        for sec in range(82, 95):
            activity.observe(replace(track, position=110 + sec - 81), sec, 1000 + sec)
        activity.scrobbler.enqueue.assert_called_once()
        activity.history.append.assert_called_once()

    def test_long_track_uses_four_minutes_and_short_track_does_not_scrobble(self):
        for duration, expected in [(1000, 1), (20, 0)]:
            activity = f.Activity(threading.Event(), Mock(), f.load_config(), amui.THEMES["nocturne"])
            activity.history.append = Mock()
            activity.scrobbler.enqueue = Mock()
            for second in range(242):
                track = amui.Track(identity="song", title="T", artist="A", length=duration, position=second, status="Playing")
                activity.observe(track, second, second + 1000)
            self.assertEqual(activity.scrobbler.enqueue.call_count, expected)

    def test_scrobble_payloads_and_signature(self):
        scrobbler = f.Scrobbler(threading.Event(), f.load_config()["scrobble"])
        scrobbler.credentials = {"listenbrainz": {"token": "fixture"},
            "lastfm": {"api_key": "key", "secret": "secret", "session_key": "session"}}
        event = dict(provider="listenbrainz", timestamp=1000, title="Title", artist="Artist", album="Album", duration=200)
        with patch.object(f, "json_request", return_value={"status": "ok"}) as request:
            scrobbler.submit(event)
            args = request.call_args.args
            self.assertEqual(args[1]["payload"][0]["listened_at"], 1000)
            self.assertEqual(args[2]["Authorization"], "Token fixture")
        with patch.object(f, "json_request", return_value={"scrobbles": {"@attr": {"accepted": "1"}}}) as request:
            scrobbler.submit({**event, "provider": "lastfm"})
            params = request.call_args.args[1]
            expected = hashlib.md5(("".join(k + str(params[k]) for k in sorted(params)
                                           if k not in ("format", "api_sig")) + "secret").encode()).hexdigest()
            self.assertEqual(params["api_sig"], expected)
            self.assertNotIn("secret", params)

    def test_scrobbling_opt_in_and_shutdown_persistence(self):
        stop = threading.Event()
        config = f.load_config()["scrobble"]
        self.assertEqual(config["providers"], [])
        config["providers"] = ["listenbrainz"]
        scrobbler = f.Scrobbler(stop, config, Path(self.tmp.name) / "pending.json")
        scrobbler.enqueue(amui.Track(title="T", artist="A", length=300), 1000)
        stop.set()
        with patch.object(f, "json_request") as request:
            scrobbler.run()
        request.assert_not_called()
        saved = json.loads(scrobbler.path.read_text())
        self.assertEqual(len(saved), 1)
        self.assertNotIn("token", saved[0])

    def test_layout_with_queue_focus_help_and_prompts(self):
        for h, w in [(22, 42), (24, 80), (35, 112), (40, 140), (60, 200)]:
            for mode in ("queue", "help", "search", "focus"):
                ui = make_ui(h, w)
                ui.extras = Mock(items=[(f"Track {n}", "Artist") for n in range(5)], label="MPRIS",
                                 identity=ui.player.track.identity, shuffle=True, repeat="Track", queue_view=None)
                ui.key({"queue": "Q", "help": "?", "search": "/", "focus": "f"}[mode])
                ui.render()
                self.assertTrue(ui.screen.cells)


class CiderHTTPTests(unittest.TestCase):
    def test_real_http_token_queue_and_shuffle_repeat_routes(self):
        requests = []
        class Server(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                requests.append((self.path, self.headers.get("apptoken")))
                if self.headers.get("apptoken") != "fixture-token":
                    self.send_response(403)
                    self.end_headers()
                    return
                values = {"now-playing": {"info": {"name": "Now", "artistName": "Artist", "playParams": {"id": "2"}, "shuffleMode": 1, "repeatMode": 2}},
                          "queue": [{"id": "2", "attributes": {"name": "Now", "artistName": "Artist"}},
                                    {"id": "3", "attributes": {"name": "Next", "artistName": "Artist"}}]}
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(values.get(self.path.rsplit("/", 1)[-1], {})).encode())
            def do_POST(self):
                self.do_GET()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Server)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conf = f.load_config()
            conf["cider"] = {"url": f"http://127.0.0.1:{server.server_port}", "token_file": "/nonexistent-amui-test-token"}
            track = amui.Track(player="fixture", identity="song", title="Now", artist="Artist")
            extras = f.Extras(threading.Event(), Mock(track=track), conf)
            with patch.dict(os.environ, {"AMUI_CIDER_TOKEN": "fixture-token"}), patch.object(f, "bus", return_value=None):
                extras.poll(track)
                self.assertEqual(extras.items, [("Next", "Artist")])
                self.assertEqual((extras.shuffle, extras.repeat), (True, "Playlist"))
                extras.api.request("toggle-shuffle", {})
                extras.api.request("toggle-repeat", {})
            self.assertTrue(all(token == "fixture-token" for _, token in requests))
            self.assertEqual(requests[-1][0], "/api/v1/playback/toggle-repeat")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
