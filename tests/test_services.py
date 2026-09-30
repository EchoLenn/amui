"""Timer boundaries and safe optional desktop notifications, without account writes."""
from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_amui import amui
from services import DesktopNotifications, SleepTimer


class ServiceTests(unittest.TestCase):
    def track(self, **changes):
        return replace(amui.Track(player="chromium.instance1", identity="song1", title="Title",
                                  artist="Artist", album="Album", status="Playing", sampled=100,
                                  position=20, length=180), **changes)

    def test_countdown_uses_monotonic_and_pauses_once(self):
        timer = SleepTimer()
        timer.arm(15, self.track(), now=100)
        self.assertEqual(timer.label(now=110), "Z 14:50")
        self.assertIsNone(timer.tick(self.track(), now=999))
        self.assertEqual(timer.tick(self.track(), now=1000), ("chromium.instance1", "pause"))
        self.assertIsNone(timer.tick(self.track(), now=1001))
        self.assertFalse(timer.active)

    def test_countdown_continues_while_paused_and_never_starts_playback(self):
        timer = SleepTimer()
        timer.arm(15, self.track(), now=100)
        self.assertIsNone(timer.tick(self.track(status="Paused"), now=500))
        self.assertEqual(timer.remaining(now=500), 500)
        self.assertIsNone(timer.tick(self.track(status="Paused"), now=1000))
        self.assertFalse(timer.active)

    def test_countdown_follows_playlist_but_cancels_on_other_player(self):
        timer = SleepTimer()
        timer.arm(15, self.track(), now=100)
        self.assertIsNone(timer.tick(self.track(identity="song2"), now=200))
        self.assertTrue(timer.active)
        self.assertIsNone(timer.tick(self.track(player="spotify"), now=1000))
        self.assertFalse(timer.active)

    def test_end_song_handles_duration_boundary_and_repeat(self):
        for next_track in (self.track(position=180, sampled=260),
                           self.track(identity="song2", position=0, sampled=260),
                           self.track(position=0, sampled=260)):
            with self.subTest(next_track=next_track):
                timer = SleepTimer()
                timer.arm(track=self.track(), end=True, now=100)
                self.assertEqual(timer.label(), "Z fin de canción")
                self.assertEqual(timer.tick(next_track, now=260), ("chromium.instance1", "pause"))
                self.assertFalse(timer.active)

    def test_end_song_waits_while_paused_and_cancel_on_early_manual_skip(self):
        timer = SleepTimer()
        timer.arm(track=self.track(), end=True, now=100)
        self.assertIsNone(timer.tick(self.track(status="Paused", position=25, sampled=105), now=105))
        self.assertIsNone(timer.tick(self.track(status="Paused", position=25, sampled=900), now=900))
        self.assertTrue(timer.active)
        self.assertIsNone(timer.tick(self.track(identity="song2", sampled=901), now=901))
        self.assertFalse(timer.active)

    def test_end_song_backward_seek_and_temporary_missing_metadata(self):
        timer = SleepTimer()
        timer.arm(track=self.track(position=120), end=True, now=100)
        self.assertIsNone(timer.tick(self.track(position=10, sampled=110), now=110))
        missing = amui.metadata_track("chromium.instance1", "", self.track())
        self.assertTrue(missing.identity)
        self.assertIsNone(timer.tick(missing, now=111))
        self.assertTrue(timer.active)
        self.assertIsNone(timer.tick(self.track(position=20, sampled=120), now=120))
        self.assertTrue(timer.active)

    def test_timer_validation_and_cancel(self):
        timer = SleepTimer()
        for kwargs in ({"minutes": 0}, {"minutes": True}, {"minutes": float("inf")},
                       {"minutes": 15, "track": self.track(player="")},
                       {"end": True, "track": self.track(length=0)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                timer.arm(track=kwargs.pop("track", self.track()), **kwargs)
        timer.arm(30, self.track(), now=100)
        timer.cancel()
        self.assertEqual(timer.label(), "")
        self.assertIsNone(timer.tick(self.track(), now=10000))

    def test_notification_disabled_or_unavailable_does_not_spawn(self):
        with patch("services.shutil.which", return_value=None), patch("services.subprocess.Popen") as spawn:
            self.assertFalse(DesktopNotifications().update(self.track()))
            self.assertFalse(DesktopNotifications(True).update(self.track()))
            spawn.assert_not_called()

    def test_notification_safe_markup_args_dedup_and_cached_art(self):
        process = Mock()
        process.poll.return_value = 0
        with tempfile.TemporaryDirectory() as directory, \
             patch("services.shutil.which", return_value="/usr/bin/notify-send"), \
             patch("services.subprocess.Popen", return_value=process) as spawn:
            art = Path(directory) / "-cover.png"
            art.write_bytes(b"fixture")
            notifications = DesktopNotifications(True)
            track = self.track(title="--urgency=critical <Title>", artist="A & B", album='"Album"')
            self.assertTrue(notifications.update(track, art, now=100))
            args = spawn.call_args.args[0]
            self.assertEqual(args[-3:], ["--", "--urgency=critical &lt;Title&gt;", "A &amp; B\n&quot;Album&quot;"])
            self.assertEqual(args[args.index("--icon") + 1], str(art))
            self.assertIs(spawn.call_args.kwargs["stdin"], subprocess.DEVNULL)
            self.assertFalse(notifications.update(track, art, now=101))
            self.assertEqual(spawn.call_count, 1)
            self.assertTrue(notifications.update(replace(track, identity="song2"), now=102))
            self.assertEqual(spawn.call_count, 2)
            self.assertIsNotNone(notifications.process)
            notifications.close()
            self.assertIsNone(notifications.process)

    def test_notifications_wait_for_metadata_playback_and_child_reaping(self):
        process = Mock()
        process.poll.return_value = None
        with patch("services.shutil.which", return_value="/usr/bin/notify-send"), \
             patch("services.subprocess.Popen", return_value=process) as spawn:
            notifications = DesktopNotifications(True)
            self.assertFalse(notifications.update(self.track(title=""), now=100))
            self.assertFalse(notifications.update(self.track(status="Paused"), now=100))
            self.assertTrue(notifications.update(self.track(), now=100))
            self.assertFalse(notifications.update(self.track(identity="song2"), now=101))
            self.assertFalse(notifications.update(self.track(identity="song2"), now=105))
            process.kill.assert_called_once()
            process.poll.return_value = 0
            self.assertTrue(notifications.update(self.track(identity="song2"), now=106))
            self.assertEqual(spawn.call_count, 2)

    def test_notification_spawn_failure_is_retryable(self):
        with patch("services.shutil.which", return_value="/usr/bin/notify-send"), \
             patch("services.subprocess.Popen", side_effect=OSError):
            notifications = DesktopNotifications(True)
            self.assertFalse(notifications.update(self.track()))
            self.assertIsNone(notifications.last)


if __name__ == "__main__":
    unittest.main()
