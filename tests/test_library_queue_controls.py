"""Queue mutations and saved library states, without changing a live account."""
import threading
import time
import unittest
from unittest.mock import Mock, patch

from test_amui import amui
import features as f


class FakeCider:
    def __init__(self, track):
        self.info = dict(name=track.title, artistName=track.artist,
                         playParams={"id": "current", "kind": "song"},
                         inFavorites=True, inLibrary=True)
        self.items = [dict(id=ident, type="song", attributes=dict(name=ident, artistName=track.artist))
                      for ident in ("history", "older", "current", "next", "last")]
        self.items[2]["attributes"]["name"] = track.title
        self.favorite, self.library = False, False
        self.commands = []
        self.apply_commands = True
        self.music_paths = []

    def request(self, endpoint, payload=None):
        if endpoint == "now-playing":
            return {"info": self.info}
        if endpoint == "queue":
            return {"items": list(self.items), "position": 2}
        self.commands.append((endpoint, payload))
        if self.apply_commands:
            if endpoint == "queue/remove-by-index":
                self.items.pop(payload["index"])
            elif endpoint == "add-to-library":
                self.library = True
        return {"status": "ok"}

    def music(self, path):
        self.music_paths.append(path)
        if path == "/v1/me/storefront":
            return {"data": [{"id": "mx"}]}
        ident = path.partition("?")[0].rsplit("/", 1)[1]
        return {"data": [{"id": ident, "attributes": {
            "inFavorites": self.favorite, "inLibrary": self.library}}]}

    def message(self, kind, data):
        self.commands.append((kind, data))
        if self.apply_commands:
            self.favorite = data["state"]


class LibraryQueueControlsTests(unittest.TestCase):
    def setUp(self):
        self.track = amui.Track(player="test", identity="track", title="Current", artist="Artist")
        self.player = Mock(track=self.track)
        self.stop = threading.Event()
        self.extra = f.Extras(self.stop, self.player, f.load_config())
        self.extra.api = FakeCider(self.track)
        self.extra._publish_queue(self.extra.api.request("queue"), self.extra.api.info, self.track)

    def test_delete_uses_absolute_zero_based_index_preserving_current_and_history(self):
        notice = self.extra.queue_action(self.extra.queue_view, 0, "delete")
        self.assertEqual(self.extra.api.commands, [("queue/remove-by-index", {"index": 3})])
        self.assertEqual([row["id"] for row in self.extra.api.items], ["history", "older", "current", "last"])
        self.assertIn("eliminada", notice)
        self.assertEqual(self.extra.items, [("last", "Artist")])

    def test_clear_pending_deletes_descending_without_clear_entire_queue(self):
        notice = self.extra.queue_action(self.extra.queue_view, 0, "clear_pending")
        self.assertEqual(self.extra.api.commands, [
            ("queue/remove-by-index", {"index": 4}), ("queue/remove-by-index", {"index": 3})])
        self.assertEqual([row["id"] for row in self.extra.api.items], ["history", "older", "current"])
        self.assertEqual(self.extra.items, [])
        self.assertIn("vaciada", notice)

    def test_changed_view_does_not_delete_other_song(self):
        self.extra.api.items[3], self.extra.api.items[4] = self.extra.api.items[4], self.extra.api.items[3]
        self.assertIn("cola cambió", self.extra.queue_action(self.extra.queue_view, 0, "delete"))
        self.assertEqual(self.extra.api.commands, [])

    def test_changed_track_during_clear_stops_before_current_can_be_deleted(self):
        request = self.extra.api.request
        def changed(endpoint, payload=None):
            response = request(endpoint, payload)
            if endpoint == "queue/remove-by-index":
                self.player.track = amui.replace(self.track, identity="new", title="New")
            return response
        self.extra.api.request = changed
        with self.assertRaisesRegex(ValueError, "canción cambió"):
            self.extra.queue_action(self.extra.queue_view, 0, "clear_pending")
        self.assertEqual(self.extra.api.commands, [("queue/remove-by-index", {"index": 4})])
        self.assertEqual(self.extra.api.items[2]["id"], "current")

    def test_dispatch_acknowledgement_is_not_a_confirmed_delete(self):
        self.extra.api.apply_commands = False
        with patch.object(self.stop, "wait", return_value=False):
            notice = self.extra.queue_action(self.extra.queue_view, 0, "clear_pending")
        self.assertIn("no confirmó", notice)
        self.assertEqual(len(self.extra.api.commands), 1)
        self.assertEqual(len(self.extra.api.items), 5)

    def test_malformed_queue_is_refused(self):
        for data in (None, {"items": "bad"}, [None], [{"attributes": "bad"}]):
            with self.assertRaises(ValueError):
                f.queue_signature(data)
            self.assertEqual(f.cider_queue(data, self.extra.api.info)[0], [])

    def test_favorite_uses_real_bridge_and_confirmed_saved_state_not_rating(self):
        self.assertIn("añadido", self.extra.library_action(self.track, "favorite"))
        message, body = self.extra.api.commands[0]
        self.assertEqual(message, "amui:favorite")
        self.assertEqual((body["id"], body["type"], body["state"]), ("current", "songs", True))
        self.assertTrue(body["request"])
        self.assertEqual((self.extra.favorite, self.extra.library_identity), (True, "track"))
        self.assertIn("retirado", self.extra.library_action(self.track, "favorite"))
        self.assertFalse(self.extra.favorite)
        self.assertEqual(len({body["request"], self.extra.api.commands[1][1]["request"]}), 2)
        self.assertTrue(all("set-rating" not in call[0] for call in self.extra.api.commands))

    def test_unconfirmed_favorite_does_not_change_indicator_or_claim_success(self):
        self.extra.api.apply_commands = False
        with patch.object(self.stop, "wait", return_value=False):
            notice = self.extra.library_action(self.track, "favorite")
        self.assertIn("activa el complemento", notice)
        self.assertFalse(self.extra.favorite)
        self.assertFalse(self.extra.library)

    def test_add_library_confirmed_and_duplicate_add_is_noop(self):
        self.assertIn("añadida", self.extra.library_action(self.track, "add"))
        self.assertTrue(self.extra.library)
        self.assertIn("ya está", self.extra.library_action(self.track, "add"))
        self.assertEqual(self.extra.api.commands, [("add-to-library", {})])

    def test_optimistic_info_is_ignored_and_missing_state_is_unknown(self):
        self.extra._library_state(self.extra.api.info, self.track)
        self.assertFalse(self.extra.favorite)
        self.assertFalse(self.extra.library)
        self.assertTrue(any("extend=inFavorites" in path for path in self.extra.api.music_paths))
        self.extra.api.music = Mock(return_value={"data": [{"id": "current", "attributes": {}}]})
        notice = self.extra.library_action(self.track, "favorite")
        self.assertIn("no confirmó", notice)
        self.assertIsNone(self.extra.favorite)
        self.assertEqual(self.extra.api.commands, [])

    def test_library_identity_is_checked_and_library_song_is_addressed_correctly(self):
        self.assertIn("cambió", self.extra.library_action(amui.replace(self.track, identity="old"), "add"))
        self.assertEqual(self.extra.api.commands, [])
        self.extra.api.info["playParams"] = {"id": "i.example", "kind": "song", "isLibrary": True}
        self.extra._confirmed_library_state(self.extra.api.info, self.track)
        self.assertTrue(self.extra.library)
        self.assertTrue(self.extra.api.music_paths[-1].startswith("/v1/me/library/songs/i.example?"))

    def test_message_endpoint_carries_existing_app_auth(self):
        api = f.CiderAPI({"url": "http://127.0.0.1:10767", "token_file": "unused"})
        with patch.dict(f.os.environ, {"AMUI_CIDER_TOKEN": "test-token"}), \
             patch.object(f, "json_request", return_value={"status": "success"}) as request:
            api.message("amui:favorite", {"id": "1", "type": "songs", "state": True, "request": "test"})
        self.assertEqual(request.call_args.args[0], "http://127.0.0.1:10767/api/v1/messages/message")
        self.assertEqual(request.call_args.args[2], {"apptoken": "test-token"})

    def test_unloaded_verified_cider_keeps_transport_and_does_not_invent_current_queue(self):
        self.player.track = amui.Track(player="chromium.instance123", identity="empty")
        self.extra.api.info = {"inFavorites": False, "inLibrary": True, "shuffleMode": 0, "repeatMode": 0}
        request = self.extra.api.request
        self.extra.api.request = Mock(side_effect=lambda endpoint, payload=None:
            {"volume": .5} if endpoint == "volume" else request(endpoint, payload))
        self.extra.api.music = Mock(side_effect=AssertionError("No current song to query"))
        with patch.object(f, "bus", return_value=None), patch.object(f, "is_cider_player", return_value=True):
            self.extra.poll(self.player.track)
        self.assertTrue(self.extra.api_available)
        self.assertEqual((self.extra.volume, self.extra.shuffle, self.extra.repeat), (.5, False, "None"))
        self.assertEqual(self.extra.now_playing, {})
        self.assertEqual(self.extra.items, [])
        self.assertIsNone(self.extra.queue_view)
        self.assertEqual((self.extra.favorite, self.extra.library, self.extra.library_identity), (None, None, ""))
        self.assertIn("sin canción cargada", self.extra.label)
        self.extra.api.music.assert_not_called()
        self.assertFalse(any(call.args[0] == "queue" for call in self.extra.api.request.call_args_list))

    def test_unloaded_other_chromium_does_not_gain_cider_controls(self):
        self.player.track = amui.Track(player="chromium.instance123", identity="empty")
        self.extra.api.info = {"shuffleMode": 0, "repeatMode": 0}
        with patch.object(f, "bus", return_value=None), patch.object(f, "is_cider_player", return_value=False):
            self.extra.poll(self.player.track)
        self.assertFalse(self.extra.api_available)
        self.assertIsNone(self.extra.queue_view)
        self.assertIsNone(self.extra.volume)

    def test_bad_optional_modes_do_not_disable_connected_unloaded_volume(self):
        self.player.track = amui.Track(player="chromium.instance123", identity="empty")
        self.extra.api.request = Mock(side_effect=lambda endpoint, payload=None:
            {"info": {"shuffleMode": "bad", "repeatMode": True}} if endpoint == "now-playing" else
            {"volume": .5} if endpoint == "volume" else {"value": "bad"})
        with patch.object(f, "bus", return_value=None), patch.object(f, "is_cider_player", return_value=True):
            self.extra.poll(self.player.track)
        self.assertTrue(self.extra.api_available)
        self.assertEqual(self.extra.volume, .5)
        self.assertIsNone(self.extra.shuffle)
        self.assertIsNone(self.extra.repeat)

    def test_malformed_and_offline_api_are_not_connected(self):
        self.player.track = amui.Track(player="chromium.instance123", identity="empty")
        for malformed in (None, [], {"info": ["bad"]}):
            self.extra.api.request = Mock(return_value=malformed)
            with patch.object(f, "bus", return_value=None), patch.object(f, "is_cider_player", return_value=True):
                self.extra.poll(self.player.track)
            self.assertFalse(self.extra.api_available)
        self.extra.api.request = Mock(side_effect=OSError("offline"))
        with patch.object(f, "bus", return_value=None):
            self.extra.poll(self.player.track)
        self.assertFalse(self.extra.api_available)

    def test_music_browser_does_not_accept_missing_playback_acknowledgement(self):
        for malformed in (None, {}, [], {"status": "error"}):
            stop = threading.Event()
            browser = f.MusicBrowser(stop, f.load_config())
            browser.api.request = Mock(return_value=malformed)
            browser.thread.start()
            try:
                browser.choose({"type": "songs", "id": "1", "title": "Song"})
                deadline = time.monotonic() + 2
                while browser.busy and time.monotonic() < deadline:
                    stop.wait(.01)
                self.assertFalse(browser.busy)
                self.assertIn("No se pudo", browser.label)
            finally:
                stop.set()
                browser.thread.join(1)


if __name__ == "__main__":
    unittest.main()
