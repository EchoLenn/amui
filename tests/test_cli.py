"""Headless CLI acceptance checks; never call live playback services."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_amui import amui
import features as f


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {
            "XDG_CONFIG_HOME": self.tmp.name,
            "XDG_CACHE_HOME": self.tmp.name,
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def invoke(self, *args, query=None, run=None, playerctl=True):
        """Exercise argument parsing and output with background work forbidden."""
        output, errors = io.StringIO(), io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(amui.sys, "argv", ["amui", *args]))
            stack.enter_context(patch.object(amui.sys, "stdout", output))
            stack.enter_context(patch.object(amui.sys, "stderr", errors))
            stack.enter_context(patch.object(amui.shutil, "which", return_value="/fixture/playerctl" if playerctl else None))
            stack.enter_context(patch.object(amui, "command", query or Mock(return_value="")))
            stack.enter_context(patch.object(amui.subprocess, "run", run or Mock(side_effect=AssertionError("Unexpected process"))))
            stack.enter_context(patch.object(amui.threading.Thread, "start", side_effect=AssertionError("Started background worker")))
            stack.enter_context(patch.object(amui.curses, "wrapper", side_effect=AssertionError("Opened curses")))
            for service in ("Activity", "History", "Lyrics", "Spectrum", "MusicBrowser"):
                stack.enter_context(patch.object(amui, service, side_effect=AssertionError("Started " + service)))
            stack.enter_context(patch.object(amui, "cider_artwork", side_effect=AssertionError("Downloaded artwork")))
            try:
                code = amui.main()
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def query(self, names=None, title="Cancio\u0301n", length=200, position=90, statuses=None):
        names = names or ["chromium.instance1"]
        statuses = statuses or {name: "Playing" for name in names}
        raw = amui.SEP.join(("/fixture/track", title, "Björk", "Álbum", "file:///fixture/cover", str(length*1_000_000)))
        def response(*args):
            if args == ("playerctl", "-l"):
                return "\n".join(names)
            self.assertEqual(args[:2], ("playerctl", "-p"))
            self.assertIn(args[2], names)
            return {"status": statuses[args[2]], "metadata": raw,
                    "position": str(position), "volume": "0.4"}[args[3]]
        return Mock(side_effect=response)

    def test_status_is_single_line_unicode_json_without_ui_or_background_work(self):
        with patch.object(amui.time, "monotonic", return_value=100):
            code, output, errors = self.invoke("--status", query=self.query())
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(len(output.splitlines()), 1)
        data = json.loads(output)
        self.assertEqual((data["title"], data["artist"], data["album"], data["status"]),
                         ("Canción", "Björk", "Álbum", "Playing"))
        self.assertIn("Björk", output)
        self.assertAlmostEqual(data["progress"], .45)
        self.assertEqual((data["position"], data["duration"], data["volume"]), (90, 200, .4))
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_status_without_player_returns_stopped_json_and_unknown_duration_is_zero(self):
        code, output, errors = self.invoke("--status")
        data = json.loads(output)
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual((data["player"], data["title"], data["status"], data["progress"]), ("", "", "Stopped", 0))
        with patch.object(amui.time, "monotonic", return_value=100):
            code, output, errors = self.invoke("--status", query=self.query(length=0, position=10))
        data = json.loads(output)
        self.assertEqual((code, errors, data["duration"], data["progress"], data["position"]), (0, "", 0, 0, 10))

    def test_status_clamps_progress_and_exact_player_selection(self):
        names = ["chromium.instance1", "chromium.instance10", "vlc"]
        query = self.query(names, position=500)
        with patch.object(amui.time, "monotonic", return_value=100):
            code, output, errors = self.invoke("--status", "--player", "vlc", query=query)
        data = json.loads(output)
        self.assertEqual((code, errors, data["player"], data["position"], data["progress"]), (0, "", "vlc", 200, 1))
        selected = [call.args[2] for call in query.call_args_list if len(call.args) > 2]
        self.assertEqual(set(selected), {"vlc"})
        code, output, errors = self.invoke("--status", "--player", "chromium.instance", query=self.query(names))
        self.assertEqual(json.loads(output)["player"], "")

    def test_status_recovers_empty_cider_metadata_without_artwork_download(self):
        info = {"name": "Recovered", "artistName": "Artist", "albumName": "Album",
                "durationInMillis": 180000, "currentPlaybackTime": 30, "playParams": {"id": "123"}}
        def response(endpoint, payload=None):
            self.assertIsNone(payload, "Status must only read Cider state")
            return {"now-playing": {"info": info}, "volume": {"volume": .37}}[endpoint]
        with patch.object(amui, "is_cider_player", return_value=True), \
             patch.object(f.CiderAPI, "request", side_effect=response) as request, \
             patch.object(amui.time, "monotonic", return_value=100):
            code, output, errors = self.invoke("--status", query=self.query(title="", length=0))
        data = json.loads(output)
        self.assertEqual((code, errors, data["title"], data["duration"]), (0, "", "Recovered", 180))
        self.assertEqual((data["volume"], data["position"]), (.37, 30))
        self.assertEqual([call.args for call in request.call_args_list], [("now-playing",), ("volume",)])

    def test_remote_controls_use_selected_playing_player_and_report_errors(self):
        names = ["vlc", "chromium.instance1", "chromium.instance2"]
        statuses = {"vlc": "Playing", "chromium.instance1": "Paused", "chromium.instance2": "Playing"}
        for option, command in (("--next", "next"), ("--prev", "previous"), ("--toggle", "play-pause")):
            with self.subTest(option=option):
                run = Mock(return_value=Mock(returncode=0))
                code, output, errors = self.invoke(option, query=self.query(names, statuses=statuses), run=run)
                self.assertEqual((code, output, errors), (0, "", ""))
                self.assertEqual(run.call_args.args[0], ["playerctl", "-p", "chromium.instance2", command])
        for outcome in (Mock(returncode=1), subprocess.TimeoutExpired("playerctl", 2)):
            run = Mock(side_effect=outcome) if isinstance(outcome, Exception) else Mock(return_value=outcome)
            code, output, errors = self.invoke("--next", query=self.query(), run=run)
            self.assertEqual((code, output), (1, ""))
            self.assertIn("amui:", errors)

    def test_connected_cider_remote_controls_use_api_even_when_mpris_is_unloaded(self):
        for option, endpoint in (("--next", "next"), ("--prev", "previous"), ("--toggle", "playpause")):
            calls = []
            def response(path, payload=None):
                calls.append((path, payload))
                if path == "now-playing":
                    return {"status": "ok", "info": {"shuffleMode": 0, "repeatMode": 0}}
                return {"status": "ok"}
            with patch.object(amui, "is_cider_player", return_value=True), \
                 patch.object(f.CiderAPI, "request", side_effect=response), \
                 patch.object(f.Extras, "poll"):
                code, output, errors = self.invoke(option, query=self.query(title="", length=0))
            self.assertEqual((code, output, errors), (0, "", ""))
            self.assertEqual([call for call in calls if call[1] is not None], [(endpoint, {})])
            self.assertIn(("active", None), calls)

    def test_status_reads_volume_without_inventing_track_from_empty_cider_info(self):
        def response(endpoint, payload=None):
            self.assertIsNone(payload)
            return {"now-playing": {"status": "ok", "info": {"inFavorites": True}},
                    "volume": {"volume": .25}}[endpoint]
        with patch.object(amui, "is_cider_player", return_value=True), \
             patch.object(f.CiderAPI, "request", side_effect=response):
            code, output, errors = self.invoke("--status", query=self.query(title="", length=0))
        data = json.loads(output)
        self.assertEqual((code, errors, data["title"], data["duration"], data["volume"]), (0, "", "", 0, .25))

    def test_missing_player_or_dependency_and_invalid_arguments_are_nonzero(self):
        for args, playerctl, code in ((("--next",), True, 1), (("--status",), False, 1),
                                       (("--status", "--toggle"), True, 2), (("--next", "--prev"), True, 2),
                                       (("--unknown-option",), True, 2)):
            with self.subTest(args=args):
                status, output, errors = self.invoke(*args, playerctl=playerctl)
                self.assertEqual((status, output), (code, ""))
                self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
