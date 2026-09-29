#!/usr/bin/env python3
"""amui — Cider / MPRIS listening room. Python standard library only."""
import argparse
import bisect
import curses
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace

VERSION = "0.2.0"
SEP = "\x1f"
THEMES = {
    "nocturne": (234, 255, 244, 239, 211, 80, 183),
    "ember": (234, 230, 244, 239, 209, 222, 173),
    "ice": (234, 255, 244, 239, 81, 153, 111),
}


def clean(value):
    return "".join(c for c in str(value) if not unicodedata.category(c).startswith("C"))


def width(text):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def clip(text, limit):
    text = clean(text)
    if width(text) <= limit:
        return text
    out = ""
    for c in text:
        if width(out + c) > max(0, limit - 1):
            break
        out += c
    return out + ("…" if limit > 0 else "")


def number(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (ValueError, TypeError):
        return default


def clock(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def command(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=2)
        return result.stdout.rstrip("\r\n") if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


@dataclass(frozen=True)
class Track:
    player: str = ""
    identity: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    art: str = ""
    length: float = 0
    position: float = 0
    volume: float = .5
    status: str = "Stopped"
    sampled: float = 0

    def elapsed(self):
        pos = self.position + (time.monotonic() - self.sampled if self.status == "Playing" else 0)
        return max(0, min(pos, self.length) if self.length else pos)

    def lyrics_key(self):
        return (self.title, self.artist, self.album, round(self.length))


def metadata_track(player, raw, old):
    fields = raw.split(SEP)
    fields += [""] * (6 - len(fields))
    ident, title, artist, album, art, duration = fields[:6]
    identity = "|".join((player, ident, title, artist, album))
    length = old.length if identity == old.identity else 0
    micros = number(duration)
    if 0 < micros < 86400000000:
        length = micros / 1000000
    return Track(player=player, identity=identity, title=clean(title),
                 artist=clean(artist), album=clean(album), art=art, length=length)


class Player:
    def __init__(self, stop, explicit=None):
        self.stop, self.explicit = stop, explicit
        self.track = Track()
        self.actions = queue.Queue(maxsize=32)
        self.saved_volume = .5
        self.notice = ""
        self.thread = threading.Thread(target=self.run, daemon=True)

    def send(self, action):
        if self.track.player:
            try:
                self.actions.put_nowait((self.track.player, action))
            except queue.Full:
                pass

    def act(self, player, action):
        args = {
            "toggle": ["play-pause"], "next": ["next"], "previous": ["previous"],
            "forward": ["position", "5+"], "back": ["position", "5-"],
            "restart": ["position", "0"],
        }
        if action in ("up", "down", "mute"):
            vol = number(command("playerctl", "-p", player, "volume"), self.track.volume)
            if action == "mute":
                if vol > .001:
                    self.saved_volume, vol = vol, 0
                else:
                    vol = self.saved_volume
            else:
                vol = max(0, min(1, vol + (.05 if action == "up" else -.05)))
            args[action] = ["volume", str(vol)]
        try:
            result = subprocess.run(["playerctl", "-p", player, *args[action]],
                                    capture_output=True, text=True, timeout=2)
            self.notice = "" if result.returncode == 0 else "Cider no aceptó el control"
        except (OSError, subprocess.TimeoutExpired):
            self.notice = "MPRIS no respondió"

    def run(self):
        while not self.stop.is_set():
            try:
                while True:
                    player, action = self.actions.get_nowait()
                    self.act(player, action)
            except queue.Empty:
                pass
            names = command("playerctl", "-l").splitlines()
            names = [n for n in names if n == self.explicit] if self.explicit else [
                n for n in names if n.startswith("chromium.instance")]
            states = [(n, command("playerctl", "-p", n, "status")) for n in names]
            player, status = next((p for p in states if p[1] == "Playing"),
                                  states[0] if states else ("", "Stopped"))
            if player:
                raw = command("playerctl", "-p", player, "metadata", "--format", SEP.join(
                    "{{" + key + "}}" for key in ("mpris:trackid", "xesam:title", "xesam:artist",
                                                   "xesam:album", "mpris:artUrl", "mpris:length")))
                track = metadata_track(player, raw, self.track)
                pos = number(command("playerctl", "-p", player, "position"))
                sampled = time.monotonic()
                vol = number(command("playerctl", "-p", player, "volume"), .5)
                self.track = replace(track, status=status, position=pos, volume=vol, sampled=sampled)
            else:
                self.track = Track()
            self.stop.wait(.3)


def parse_lrc(text):
    entries = []
    offset = re.search(r"\[offset:([+-]?\d+)\]", text, re.I)
    shift = int(offset[1]) / 1000 if offset else 0
    for line in text.splitlines():
        stamps = list(re.finditer(r"\[(\d+):(\d+(?:\.\d+)?)\]", line))
        if stamps:
            words = clean(line[stamps[-1].end():].strip())
            for stamp in stamps:
                entries.append((int(stamp[1]) * 60 + float(stamp[2]) - shift, words))
    return sorted(entries, key=lambda entry: entry[0])


class Lyrics:
    def __init__(self, stop, enabled=True):
        self.stop, self.enabled = stop, enabled
        self.requests = queue.Queue(maxsize=1)
        self.result = (None, [], [], "Letras en espera")
        self.requested = None
        self.cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "amui/lyrics"
        self.thread = threading.Thread(target=self.run, daemon=True)

    def request(self, track, retry=False):
        if not self.enabled or not track.title or (track.lyrics_key() == self.requested and not retry):
            return
        self.requested = track.lyrics_key()
        try:
            self.requests.get_nowait()
        except queue.Empty:
            pass
        self.requests.put_nowait((track, retry))

    def fetch(self, track, retry):
        key = hashlib.sha256(json.dumps(track.lyrics_key(), ensure_ascii=False).encode()).hexdigest()
        path = self.cache / (key + ".json")
        if not retry:
            try:
                if time.time() - path.stat().st_mtime < 30 * 86400:
                    data = json.loads(path.read_text())
                    if isinstance(data, dict):
                        return data
            except (OSError, ValueError):
                pass
        params = dict(track_name=track.title, artist_name=track.artist, album_name=track.album)
        if track.length:
            params["duration"] = round(track.length)
        # Retry reissues without album. A final duration-free match is displayed
        # as plain text if the MPRIS clock disagrees with the catalog duration.
        for attempt in range(3):
            url = "https://lrclib.net/api/get?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": "amui/" + VERSION,
                                                      "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=7) as response:
                    data = json.loads(response.read(2_000_000))
                break
            except urllib.error.HTTPError as error:
                if error.code != 404 and error.code < 500:
                    raise
                if attempt == 0 and params.get("album_name"):
                    params.pop("album_name")
                elif attempt < 2 and "duration" in params:
                    params.pop("duration")
                else:
                    raise
        if not isinstance(data, dict):
            raise ValueError("Invalid lyrics response")
        try:
            self.cache.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", dir=self.cache, delete=False) as file:
                json.dump(data, file)
                temporary = Path(file.name)
            temporary.replace(path)
        except OSError:
            pass
        return data

    def run(self):
        while not self.stop.is_set():
            try:
                track, retry = self.requests.get(timeout=.2)
            except queue.Empty:
                continue
            key = track.lyrics_key()
            self.result = (key, [], [], "Buscando en LRCLIB…")
            try:
                data = self.fetch(track, retry)
                synced = parse_lrc(data.get("syncedLyrics") or "")
                plain = [clean(line) for line in (data.get("plainLyrics") or "").splitlines()]
                mismatch = track.length and number(data.get("duration")) and abs(track.length - number(data["duration"])) > 2
                if mismatch:
                    plain = plain or [line for _, line in synced]
                    synced = []
                label = "Instrumental" if data.get("instrumental") else (
                    "LRCLIB · sincronizadas" if synced else
                    "LRCLIB · texto · [ / ] desplazar" if plain else "Sin letras para esta canción")
                if mismatch and plain:
                    label = "Texto · duración MPRIS distinta · [ / ]"
                result = (key, synced, plain, label)
            except urllib.error.HTTPError as error:
                result = (key, [], [], "Sin letras en LRCLIB" if error.code == 404 else "LRCLIB no disponible · R reintentar")
            except (OSError, ValueError, TypeError):
                result = (key, [], [], "Sin conexión a LRCLIB · R reintentar")
            if key == self.requested:
                self.result = result


class Spectrum:
    """Own CAVA process and temporary config; never touches the user's config."""
    def __init__(self, stop, enabled=True, method="pulse"):
        self.stop, self.enabled, self.method = stop, enabled, method
        self.bars = [0.] * 48
        self.label = "CAVA · iniciando" if enabled else "CAVA desactivado"
        self.process = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        if not self.enabled:
            return
        if not shutil.which("cava"):
            self.label = "Instala cava para activar el espectro"
            return
        with tempfile.TemporaryDirectory(prefix="amui-cava-") as folder:
            config = Path(folder) / "config"
            config.write_text("[general]\nframerate=30\nbars=48\nautosens=1\n"
                              "[input]\nmethod=" + self.method + "\nsource=auto\n"
                              "[output]\nmethod=raw\nraw_target=/dev/stdout\ndata_format=ascii\n"
                              "ascii_max_range=1000\nbar_delimiter=59\nframe_delimiter=10\n")
            try:
                self.process = subprocess.Popen(["cava", "-p", str(config)], stdout=subprocess.PIPE,
                                                stderr=subprocess.DEVNULL, text=True)
                if self.stop.is_set():
                    self.process.terminate()
                for line in self.process.stdout:
                    if self.stop.is_set():
                        break
                    try:
                        values = [min(1., max(0., int(v) / 1000)) for v in line.strip().split(";") if v]
                    except ValueError:
                        continue
                    if len(values) == 48:
                        self.bars = values
                        self.label = "CAVA · salida del sistema"
                if not self.stop.is_set():
                    self.label = "CAVA sin señal · revisa el backend de audio"
            except OSError:
                self.label = "No se pudo iniciar CAVA"
            finally:
                self.close()

    def close(self):
        proc = self.process
        if proc:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            if proc.stdout:
                proc.stdout.close()


class Cover:
    def __init__(self):
        self.command = (["kitten", "icat"] if shutil.which("kitten") else
                        ["kitty", "+kitten", "icat"] if shutil.which("kitty") else [])
        self.enabled = bool(self.command and (os.environ.get("KITTY_WINDOW_ID") or
                                              os.environ.get("TERM") == "xterm-kitty"))
        self.last = None
        self.drawn = False

    def clear(self):
        if self.drawn:
            # Delete only this application's image, not other terminal images.
            sys.stdout.write("\033_Ga=d,d=I,i=7311,q=2;\033\\")
            sys.stdout.flush()
        self.drawn = False
        self.last = None

    def show(self, art, rect):
        if not self.enabled or not rect:
            self.clear()
            return
        path = urllib.parse.unquote(urllib.parse.urlparse(art).path) if art.startswith("file://") else art
        signature = (path, rect)
        if signature == self.last:
            return
        self.clear()
        if not path or not Path(path).is_file():
            return
        x, y, w, h = rect
        try:
            result = subprocess.run(self.command + ["--stdin=no", "--transfer-mode=file", "--silent",
                "--image-id=7311", f"--place={w}x{h}@{x}x{y}", "--scale-up", path],
                stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            self.drawn = result.returncode == 0
            if self.drawn:
                self.last = signature
        except (OSError, subprocess.TimeoutExpired):
            pass


class UI:
    def __init__(self, screen, player, lyrics, spectrum, options):
        self.screen, self.player, self.lyrics, self.spectrum = screen, player, lyrics, spectrum
        self.options = options
        self.cover = Cover()
        self.theme = options.theme
        self.show_lyrics, self.show_visual = not options.no_lyrics, not options.no_cava
        self.focus = False
        self.help = False
        self.scroll = 0
        self.offset = 0.
        self.old_identity = ""
        self.old_size = None
        self.art_rect = None
        self.palette = {}

    def colors(self):
        bg, fg, muted, border, accent, cyan, lilac = THEMES[self.theme]
        if curses.has_colors():
            curses.start_color()
            colors = [fg, muted, border, accent, cyan, lilac]
            for i, color in enumerate(colors, 1):
                curses.init_pair(i, color if curses.COLORS >= 256 else [7, 7, 4, 5, 6, 3][i-1],
                                 bg if curses.COLORS >= 256 else 0)
                self.palette[i] = curses.color_pair(i)
        self.screen.bkgd(" ", self.palette.get(1, 0))

    def text(self, y, x, text, color=1, bold=False, limit=None):
        h, w = self.screen.getmaxyx()
        if 0 <= y < h and 0 <= x < w:
            text = clip(text, min(w - x - 1, limit if limit is not None else w))
            try:
                self.screen.addstr(y, x, text, self.palette.get(color, 0) | (curses.A_BOLD if bold else 0))
            except curses.error:
                pass

    def box(self, y, x, h, w, title="", tag=""):
        self.text(y, x, "╭" + "─" * (w - 2) + "╮", 3)
        self.text(y + h - 1, x, "╰" + "─" * (w - 2) + "╯", 3)
        for row in range(y + 1, y + h - 1):
            self.text(row, x, "│", 3)
            self.text(row, x + w - 1, "│", 3)
        self.text(y, x + 3, " " + title + " ", 4, True, w - 6)
        if tag and w > width(title) + width(tag) + 12:
            self.text(y, x + w - width(tag) - 4, " " + tag + " ", 2)

    def lyrics_panel(self, y, x, h, w, track):
        self.box(y, x, h, w, "LYRICS", "LIVE" if self.lyrics.enabled else "OFF")
        key, synced, plain, label = self.lyrics.result
        if key != track.lyrics_key():
            synced, plain, label = [], [], "Buscando letras…" if track.title else "La próxima canción empieza aquí"
        if not self.lyrics.enabled:
            label = "Letras desactivadas con --no-lyrics"
        self.text(y + h - 2, x + 3, label, 2, limit=w - 6)
        if synced:
            index = bisect.bisect_right([t for t, _ in synced], track.elapsed() + self.offset) - 1
            center = y + max(2, (h - 2) // 2)
            for i, (_, line) in enumerate(synced):
                row = center + (i - index) * 2
                if y + 2 <= row < y + h - 3:
                    current = i == index
                    self.text(row, x + 3, "›" if current else " ", 4, current)
                    self.text(row, x + 5, line or "♪", 4 if current else 1 if i == index + 1 else 2,
                              current, w - 8)
        elif plain:
            self.scroll = max(0, min(self.scroll, max(0, len(plain) - (h - 5))))
            for i, line in enumerate(plain[self.scroll:self.scroll + h - 5]):
                self.text(y + 2 + i, x + 3, line, 1, limit=w - 6)
        else:
            self.text(y + h // 2 - 1, x + 3, "♪", 4, True)
            self.text(y + h // 2 + 1, x + 3, label, 2, limit=w - 6)

    def now_playing(self, y, x, h, w, track):
        self.box(y, x, h, w, "NOW PLAYING", "CIDER / MPRIS")
        cover_h = min(h - 4, 13)
        cover_w = cover_h * 2
        cover = w >= 59 and h >= 14
        tx = x + cover_w + 6 if cover else x + 3
        tw = x + w - tx - 3
        if cover:
            cy, cx = y + 2, x + 3
            self.art_rect = (cx, cy, cover_w, cover_h)
            # Text fallback occupies the same rectangle as the Kitty image.
            path = urllib.parse.unquote(urllib.parse.urlparse(track.art).path) if track.art.startswith("file://") else track.art
            if not self.cover.enabled or not path or not Path(path).is_file():
                for i in range(cover_h):
                    self.text(cy + i, cx, "░" * cover_w, 3)
                self.text(cy + cover_h // 2 - 2, cx + 3, "   ╭──────╮", 6)
                self.text(cy + cover_h // 2 - 1, cx + 3, " ╭─┤  ◉   ├─╮", 4)
                self.text(cy + cover_h // 2, cx + 3, " ╰─┤      ├─╯", 4)
                self.text(cy + cover_h // 2 + 1, cx + 3, "   ╰──────╯", 6)
        self.text(y + 2, tx, "TU SESIÓN / APPLE MUSIC", 5, True, tw)
        self.text(y + 4, tx, track.title or "Dale play a tu mundo.", 1, True, tw)
        self.text(y + 6, tx, track.artist or "Abre Cider y elige una canción", 4, True, tw)
        if h >= 12:
            self.text(y + 8, tx, track.album or "Una terminal. Toda tu música.", 2, limit=tw)
        state = "▶ REPRODUCIENDO" if track.status == "Playing" else "Ⅱ EN PAUSA" if track.player else "○ ESPERANDO CIDER"
        self.text(y + h - 3, tx, state, 5, True, tw)

    def spectrum_panel(self, y, x, h, w):
        self.box(y, x, h, w, "SPECTRUM", self.spectrum.label)
        n = min(48, (w - 6) // 2)
        span = max(1, h - 3)
        start = x + (w - n * 2) // 2
        blocks = " ▁▂▃▄▅▆▇█"
        for i in range(n):
            value = self.spectrum.bars[min(47, int(i * 48 / n))] * span
            for row in range(span):
                part = min(8, max(0, round((value - row) * 8)))
                self.text(y + h - 2 - row, start + i * 2, blocks[part],
                          5 if row < span / 3 else 6 if row < span * 2 / 3 else 4)
        if not any(self.spectrum.bars):
            self.text(y + h // 2, x + 3, self.spectrum.label, 2, limit=w - 6)

    def transport(self, y, w, track):
        self.text(y, 3, "─" * (w - 6), 3)
        pos, length = track.elapsed(), track.length
        self.text(y + 1, 3, clock(pos), 5)
        total = clock(length) if length else "--:--"
        self.text(y + 1, w - 8, total, 2)
        size = max(1, w - 23)
        filled = min(size - 1, int(pos / length * (size - 1))) if length else 0
        self.text(y + 1, 11, "━" * filled + "●", 4)
        self.text(y + 1, 12 + filled, "─" * (size - filled - 1), 3)
        vol = min(1, max(0, track.volume))
        self.text(y + 3, 3, "p  ‹‹    SPACE  ▶ / Ⅱ    n  ››", 1, True)
        label = f"{'MUTE' if vol == 0 else 'VOL'}  {'━' * round(vol * 8)}{'─' * (8 - round(vol * 8))} {vol:.0%}"
        if w >= 66:
            self.text(y + 3, w - width(label) - 4, label, 5)
        self.text(y + 5, 3, "←/→ seek   ↑/↓ vol   m mute   L letras   v cava   ? ayuda   q salir", 2, limit=w - 6)

    def render(self):
        screen, track = self.screen, self.player.track
        h, w = screen.getmaxyx()
        if (h, w) != self.old_size:
            self.cover.clear()
            screen.clear()
            self.old_size = (h, w)
        screen.erase()
        self.art_rect = None
        self.text(1, 3, "a m u i", 4, True)
        if w > 58:
            self.text(1, 16, "A LITTLE LOUDER. A LITTLE CLOSER.", 2)
        if w > 85:
            self.text(1, w - 26, f"● {self.theme.upper()}  /  {time.strftime('%H:%M')}", 5)
        if h < 22 or w < 42:
            self.text(4, 3, track.title or "amui · Cider", 1, True)
            self.text(6, 3, track.artist, 4)
            self.text(8, 3, "Amplía a 42 × 22 o más", 2)
            self.text(10, 3, "SPACE play/pausa · q salir", 5)
            screen.refresh()
            self.cover.clear()
            return
        bottom = h - 7
        content_h = bottom - 4
        if self.focus and self.show_lyrics:
            self.lyrics_panel(3, 2, content_h, w - 4, track)
        else:
            side = self.show_lyrics and w >= 112
            left_w = int(w * .57) if side else w - 4
            visual_h = min(9, max(6, content_h // 3)) if self.show_visual and content_h >= 23 else 0
            now_h = content_h - (visual_h + 1 if visual_h else 0)
            self.now_playing(3, 2, now_h, left_w, track)
            if visual_h:
                self.spectrum_panel(4 + now_h, 2, visual_h, left_w)
            if side:
                self.lyrics_panel(3, left_w + 4, content_h, w - left_w - 6, track)
        self.transport(bottom, w, track)
        if self.player.notice:
            self.text(h - 1, 3, self.player.notice, 4)
        if self.help:
            self.art_rect = None
            screen.erase()
            self.box(2, 2, h - 4, w - 4, "MAKE YOURSELF AT HOME")
            rows = ["ESPACIO  reproducir / pausar      n / p  siguiente / anterior",
                    "← → / h l  ±5 segundos           ↑ ↓ / k j  volumen",
                    "m  mute / restaurar              r  reiniciar canción",
                    "L  mostrar / ocultar letras      f  letras a pantalla completa",
                    "v  mostrar / ocultar CAVA         t  cambiar paleta",
                    "[ / ]  desplazar texto           , / .  ajustar letras ±0.5 s",
                    "R  volver a buscar letras        o  abrir Cider",
                    "q  salir                         ? / ESC  cerrar ayuda",
                    "", "CAVA escucha la salida del sistema. Letras: LRCLIB.",
                    f"Ajuste de letras: {self.offset:+.1f} s · tema: {self.theme}"]
            for i, line in enumerate(rows):
                self.text(5 + i * (2 if h >= 32 else 1), 5, line, 1 if i < 8 else 2, limit=w - 10)
        screen.refresh()
        self.cover.show(track.art, self.art_rect)

    def key(self, key):
        actions = {" ": "toggle", "n": "next", "p": "previous", "l": "forward", "h": "back",
                   "k": "up", "j": "down", "m": "mute", "r": "restart",
                   curses.KEY_RIGHT: "forward", curses.KEY_LEFT: "back",
                   curses.KEY_UP: "up", curses.KEY_DOWN: "down"}
        if key in actions:
            self.player.send(actions[key])
        elif key == "q":
            return False
        elif key in ("?", "\x1b"):
            self.help = not self.help if key == "?" else False
            self.cover.clear()
        elif key == "L":
            self.show_lyrics = not self.show_lyrics
        elif key == "f":
            self.focus = not self.focus
            self.show_lyrics = True
        elif key == "v":
            self.show_visual = not self.show_visual
        elif key == "t":
            themes = list(THEMES)
            self.theme = themes[(themes.index(self.theme) + 1) % len(themes)]
            self.colors()
            self.cover.clear()
            self.screen.clear()
        elif key in ("[", "]"):
            self.scroll = max(0, self.scroll + (-1 if key == "[" else 1))
        elif key in (",", "."):
            self.offset += -.5 if key == "," else .5
        elif key == "R":
            self.lyrics.request(self.player.track, retry=True)
        elif key == "o" and not self.player.track.player and shutil.which("cider"):
            subprocess.Popen(["cider"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        return True

    def run(self):
        curses.curs_set(0)
        self.screen.keypad(True)
        self.screen.timeout(33)
        curses.set_escdelay(25)
        self.colors()
        try:
            while not self.player.stop.is_set():
                track = self.player.track
                if track.identity != self.old_identity:
                    self.old_identity, self.scroll, self.offset = track.identity, 0, 0.
                self.lyrics.request(track)
                self.render()
                try:
                    key = self.screen.get_wch()
                except curses.error:
                    continue
                if not self.key(key):
                    break
        finally:
            self.cover.clear()


def main():
    parser = argparse.ArgumentParser(description="amui · Cider, portada, CAVA y letras sincronizadas")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--theme", choices=THEMES, default="nocturne")
    parser.add_argument("--no-lyrics", action="store_true", help="no consultar LRCLIB")
    parser.add_argument("--no-cava", action="store_true", help="no iniciar el visualizador")
    parser.add_argument("--player", help="nombre MPRIS exacto; por defecto chromium.instance*")
    parser.add_argument("--cava-input", choices=("pulse", "pipewire"), default="pulse")
    options = parser.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.exit(1, "Abre amui en una terminal interactiva (Kitty para las portadas).\n")
    if not shutil.which("playerctl"):
        parser.exit(1, "Falta playerctl. En Arch: sudo pacman -S playerctl\n")
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGHUP, lambda *_: stop.set())
    player, lyrics, spectrum = Player(stop, options.player), Lyrics(stop, not options.no_lyrics), Spectrum(
        stop, not options.no_cava, options.cava_input)
    for worker in (player, lyrics, spectrum):
        worker.thread.start()
    try:
        curses.wrapper(lambda screen: UI(screen, player, lyrics, spectrum, options).run())
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        # Terminating the producer unblocks its reader; that thread owns cleanup.
        if spectrum.process and spectrum.process.poll() is None:
            spectrum.process.terminate()
        spectrum.thread.join(timeout=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
