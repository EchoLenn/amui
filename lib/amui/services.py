"""Small services advanced by the UI loop; no playback worker or Python dependency."""
import html
import math
from pathlib import Path
import shutil
import subprocess
import time
import urllib.parse


def _position(track, now):
    """Use the same monotonic clock as MPRIS samples, including between polls."""
    position = max(0, track.position)
    if track.status == "Playing":
        position += max(0, now - track.sampled)
    return min(position, track.length) if track.length > 0 else position


class SleepTimer:
    """One-shot pause of the player selected when armed.

    Countdown continues while paused. End-song mode follows the selected song;
    an early manual skip cancels it. A natural transition or repeat observed
    between MPRIS samples pauses that same player just after the boundary.
    """
    DURATIONS = (15, 30, 45, 60)

    def __init__(self):
        self.cancel()

    @property
    def active(self):
        return bool(self.player)

    def cancel(self):
        self.player = ""
        self.identity = ""
        self.deadline = None
        self.previous = None

    def arm(self, minutes=None, track=None, *, end=False, now=None):
        if track is None or not track.player:
            raise ValueError("No hay reproductor activo")
        if end:
            if not track.identity or not math.isfinite(track.length) or track.length <= 0:
                raise ValueError("La canción necesita una duración conocida")
        elif (isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or
              not math.isfinite(minutes) or minutes <= 0):
            raise ValueError("La duración debe ser mayor que cero")
        now = time.monotonic() if now is None else now
        self.player, self.identity = track.player, track.identity
        self.deadline = None if end else now + minutes * 60
        self.previous = track

    def remaining(self, now=None):
        if not self.active or self.deadline is None:
            return None
        now = time.monotonic() if now is None else now
        return max(0, self.deadline - now)

    def label(self, now=None):
        if not self.active:
            return ""
        if self.deadline is None:
            return "Z fin de canción"
        seconds = math.ceil(self.remaining(now))
        return f"Z {seconds // 60:02d}:{seconds % 60:02d}"

    def tick(self, track, now=None):
        """Return (player, 'pause') exactly once, suitable for Player.actions."""
        if not self.active:
            return None
        now = time.monotonic() if now is None else now
        if track.player != self.player:
            self.cancel()
            return None
        expired = self.deadline is not None and now >= self.deadline
        if self.deadline is None:
            previous = self.previous
            # Unknown temporary metadata is not a different song. Wait for the
            # player poll to recover a valid identity before deciding.
            if not track.identity or not track.title:
                return None
            crossed = (previous.status == "Playing" and previous.length > 0 and
                       _position(previous, now) >= previous.length)
            if track.identity != self.identity:
                if not crossed:
                    self.cancel()
                    return None
                expired = True
            elif track.length > 0:
                # A reset near a predicted end can be repeat-one. An ordinary
                # backward seek before that boundary keeps the timer armed.
                expired = (_position(track, now) >= track.length or
                           (crossed and track.position < previous.position))
            self.previous = track
        if not expired:
            return None
        player = self.player
        self.cancel()
        return (player, "pause") if track.status == "Playing" else None


class DesktopNotifications:
    """Optional, deduplicated notify-send invocations without blocking redraws."""
    def __init__(self, enabled=False):
        self.executable = shutil.which("notify-send") if enabled else None
        self.last = None
        self.process = None
        self.started = 0

    @property
    def available(self):
        return self.executable is not None

    def _reap(self, now):
        if self.process is not None:
            if self.process.poll() is not None:
                self.process = None
            elif now - self.started >= 5:
                # A stuck desktop daemon must not accumulate subprocesses.
                self.process.kill()

    def update(self, track, art_path="", now=None):
        now = time.monotonic() if now is None else now
        self._reap(now)
        if not self.available or not track.player or not track.title or track.status != "Playing":
            return False
        key = (track.player, track.identity or (track.title, track.artist, track.album))
        if key == self.last or self.process is not None:
            return False
        args = [self.executable, "--app-name=amui"]
        if art_path:
            art_path = str(art_path)
            if art_path.startswith("file://"):
                art_path = urllib.parse.unquote(urllib.parse.urlparse(art_path).path)
            path = Path(art_path).expanduser().resolve()
            if path.is_file():
                args.extend(["--icon", str(path)])
        body = "\n".join(html.escape(text, quote=True) for text in (track.artist, track.album) if text)
        args.extend(["--", html.escape(track.title, quote=True), body])
        try:
            self.process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            return False
        self.started, self.last = now, key
        return True

    def close(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=.2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=.2)
        self.process = None
