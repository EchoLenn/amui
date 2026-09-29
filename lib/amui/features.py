"""Preferences and optional services for amui. No third-party Python packages."""
import base64
import colorsys
from collections import deque
from datetime import datetime, timezone
import fcntl
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request

KEYS = {
    "toggle": ["SPACE"], "next": ["n"], "previous": ["p"],
    "forward": ["RIGHT", "l"], "back": ["LEFT", "h"],
    "up": ["UP", "k"], "down": ["DOWN", "j"], "mute": ["m"], "restart": ["r"],
    "shuffle": ["s"], "repeat": ["e"], "quit": ["q"], "help": ["?"],
    "lyrics": ["L"], "focus": ["f"], "visualizer": ["v"], "theme": ["t"],
    "scroll_up": ["["], "scroll_down": ["]"], "offset_back": [","], "offset_forward": ["."],
    "retry": ["R"], "open": ["o"], "search": ["/"], "export": ["S"], "queue": ["Q"],
}
COLOR_NAMES = ("background", "foreground", "muted", "border", "accent", "secondary", "tertiary")


def config_dir():
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "amui"


def cache_dir():
    return Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "amui"


def rgb(index):
    if index < 16:
        return [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128),
                (128, 0, 128), (0, 128, 128), (192, 192, 192), (128, 128, 128),
                (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 255),
                (0, 255, 255), (255, 255, 255)][index]
    if index >= 232:
        return (8 + (index - 232) * 10,) * 3
    n, ramp = index - 16, (0, 95, 135, 175, 215, 255)
    return ramp[n // 36], ramp[n // 6 % 6], ramp[n % 6]


def nearest_color(color):
    return min(range(16, 256), key=lambda i: sum((a - b) ** 2 for a, b in zip(color, rgb(i))))


def parse_color(value):
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 255:
        return value
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return nearest_color(tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)))
    raise ValueError("Cada color debe ser 0–255 o #RRGGBB")


def load_config(path=None):
    path = Path(path) if path else config_dir() / "config.toml"
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError:
        if path != config_dir() / "config.toml":
            raise ValueError(f"No existe la configuración: {path}")
        data = {}
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"No se pudo leer {path}: {error}") from error
    defaults = dict(theme="nocturne", cava_input="pulse", lyrics_offset=0.,
                    lyrics=True, cava=True, queue=True, history=True, notifications=True,
                    animations=True, dynamic_palette=False, mouse=True, cover_protocol="auto",
                    export_dir=str(Path.home() / "Music/amui-lyrics"))
    allowed = set(defaults) | {"keybinds", "themes", "cider", "scrobble"}
    if set(data) - allowed:
        raise ValueError("Opciones desconocidas: " + ", ".join(sorted(set(data) - allowed)))
    conf = {**defaults, **data}
    for key, default in defaults.items():
        if isinstance(default, bool) and not isinstance(conf[key], bool):
            raise ValueError(f"{key} debe ser true o false")
        if isinstance(default, str) and not isinstance(conf[key], str):
            raise ValueError(f"{key} debe ser texto")
    if conf["cava_input"] not in ("pulse", "pipewire"):
        raise ValueError("cava_input debe ser pulse o pipewire")
    if conf["cover_protocol"] not in ("auto", "kitty", "iterm", "sixel", "none"):
        raise ValueError("cover_protocol debe ser auto, kitty, iterm, sixel o none")
    offset = conf["lyrics_offset"]
    if isinstance(offset, bool) or not isinstance(offset, (float, int)) or not math.isfinite(offset) or abs(offset) > 600:
        raise ValueError("lyrics_offset debe ser un número entre −600 y 600")
    for section in ("keybinds", "themes", "cider", "scrobble"):
        if not isinstance(conf.get(section, {}), dict):
            raise ValueError(f"[{section}] debe ser una tabla TOML")
    keys = {action: list(values) for action, values in KEYS.items()}
    for action, value in conf.get("keybinds", {}).items():
        if action not in keys:
            raise ValueError(f"Acción desconocida en keybinds: {action}")
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list) or not values or any(not isinstance(k, str) or
                (len(k) != 1 and k not in ("SPACE", "LEFT", "RIGHT", "UP", "DOWN")) or
                (len(k) == 1 and not k.isprintable()) for k in values):
            raise ValueError(f"Teclas no válidas para {action}")
        keys[action] = ["SPACE" if k == " " else k for k in values]
    assigned = {}
    for action, values in keys.items():
        for key in values:
            if key in assigned:
                raise ValueError(f"Tecla duplicada {key}: {assigned[key]} / {action}")
            assigned[key] = action
    conf["keybinds"], conf["keymap"] = keys, assigned
    themes = {}
    for name, colors in conf.get("themes", {}).items():
        if not isinstance(colors, dict) or set(colors) != set(COLOR_NAMES):
            raise ValueError(f"El tema {name} necesita: {', '.join(COLOR_NAMES)}")
        themes[name] = tuple(parse_color(colors[key]) for key in COLOR_NAMES)
    conf["themes"] = themes
    cider = conf.setdefault("cider", {})
    if set(cider) - {"url", "token_file"}:
        raise ValueError("[cider] acepta url y token_file")
    if any(not isinstance(value, str) for value in cider.values()):
        raise ValueError("[cider] requiere valores de texto")
    cider.setdefault("url", "http://127.0.0.1:10767")
    cider.setdefault("token_file", str(config_dir() / "cider.token"))
    url = urllib.parse.urlparse(cider["url"])
    if url.scheme not in ("http", "https") or url.hostname not in ("localhost", "127.0.0.1", "::1") or url.username:
        raise ValueError("La URL de Cider debe apuntar a localhost (http/https)")
    scrobble = conf.setdefault("scrobble", {})
    if set(scrobble) - {"providers", "credentials_file"}:
        raise ValueError("[scrobble] acepta providers y credentials_file")
    providers = scrobble.setdefault("providers", [])
    if not isinstance(providers, list) or any(p not in ("lastfm", "listenbrainz") for p in providers):
        raise ValueError("scrobble.providers acepta lastfm y listenbrainz")
    if len(set(providers)) != len(providers):
        raise ValueError("No repitas proveedores de scrobbling")
    scrobble.setdefault("credentials_file", str(config_dir() / "scrobble.json"))
    if not isinstance(scrobble["credentials_file"], str):
        raise ValueError("credentials_file debe ser una ruta")
    return conf


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            os.chmod(temporary, 0o600)
            json.dump(data, file, ensure_ascii=False)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def read_secret(path):
    try:
        return Path(path).expanduser().read_text().strip()
    except OSError:
        return ""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def json_request(url, payload=None, headers=None, form=False, timeout=3):
    body = None if payload is None else (urllib.parse.urlencode(payload).encode() if form
                                        else json.dumps(payload).encode())
    hdr = {"User-Agent": "amui/0.3", "Accept": "application/json", **(headers or {})}
    if body is not None:
        hdr["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    request = urllib.request.Request(url, data=body, headers=hdr)
    # Authentication headers must never be forwarded to a redirected origin.
    with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
        raw = response.read(4_000_000)
        return json.loads(raw) if raw else {}


class CiderAPI:
    def __init__(self, conf):
        self.url = conf["url"].rstrip("/")
        self.token_file = conf["token_file"]

    def request(self, endpoint, payload=None):
        token = os.environ.get("AMUI_CIDER_TOKEN") or read_secret(self.token_file)
        return json_request(self.url + "/api/v1/playback/" + endpoint, payload,
                            {"apptoken": token} if token else {})


def connect_cider(conf):
    api = CiderAPI(conf["cider"])
    print("Cider → Settings → Connectivity → API tokens: crea un token para amui.")
    token = getpass.getpass("Token de Cider (oculto): ").strip()
    if not token:
        raise ValueError("Token vacío; no se guardó nada")
    json_request(api.url + "/api/v1/playback/active", headers={"apptoken": token})
    path = Path(api.token_file).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
        file.write(token)
        temp = Path(file.name)
    os.chmod(temp, 0o600)
    temp.replace(path)
    print("Cider conectado. Token guardado con permisos privados.")


def unwrap(value):
    if isinstance(value, dict):
        if "type" in value and "data" in value:
            return unwrap(value["data"])
        return {key: unwrap(item) for key, item in value.items()}
    return [unwrap(item) for item in value] if isinstance(value, list) else value


def bus(player, method, interface, member, *args):
    try:
        result = subprocess.run(["busctl", "--user", "--json=short", "--timeout=2", method,
            "org.mpris.MediaPlayer2." + player, "/org/mpris/MediaPlayer2", interface, member, *args],
            capture_output=True, text=True, timeout=2.5)
        if result.returncode:
            return None
        return unwrap(json.loads(result.stdout))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def cider_queue(data, current):
    """Exclude history/current; don't invent an index for ambiguous duplicates."""
    items = data if isinstance(data, list) else data.get("items", data.get("queue", []))
    if not isinstance(items, list):
        return [], "Formato de cola no reconocido"
    index = data.get("position", data.get("nowPlayingItemIndex")) if isinstance(data, dict) else None
    if index is None:
        current_id = str(current.get("playParams", {}).get("id", current.get("id", "")))
        matches = []
        for i, item in enumerate(items):
            attr = item.get("attributes", item)
            item_id = str(item.get("id", attr.get("playParams", {}).get("id", "")))
            if (current_id and item_id == current_id) or (not current_id and
                    attr.get("name") == current.get("name") and attr.get("artistName") == current.get("artistName")):
                matches.append(i)
        if len(matches) != 1:
            return [], "No se puede ubicar la pista actual en la cola"
        index = matches[0]
    if not isinstance(index, int) or not -1 <= index < len(items):
        return [], "Posición de cola no disponible"
    result = []
    for item in items[index + 1:index + 6]:
        attr = item.get("attributes", item)
        result.append((str(attr.get("name", "Sin título")), str(attr.get("artistName", ""))))
    return result, "Cider API" if result else "Fin de la cola"


class Extras:
    def __init__(self, stop, player, config):
        self.stop, self.player = stop, player
        self.api = CiderAPI(config["cider"])
        self.items, self.label = [], "Consultando cola…"
        self.shuffle, self.repeat = None, None
        self.identity = ""
        self.now_playing = {}
        self.sampled = 0
        self.api_available = False
        self.thread = threading.Thread(target=self.run, daemon=True)

    def poll(self, track):
        if track.identity != self.identity:
            self.items, self.label = [], "Actualizando cola…"
            self.api_available = False
        self.identity = track.identity
        if not track.player:
            self.items, self.label = [], "Abre Cider para ver la cola"
            self.shuffle, self.repeat, self.now_playing = None, None, {}
            self.api_available = False
            return
        self.shuffle = bus(track.player, "get-property", "org.mpris.MediaPlayer2.Player", "Shuffle")
        self.repeat = bus(track.player, "get-property", "org.mpris.MediaPlayer2.Player", "LoopStatus")
        ids = bus(track.player, "get-property", "org.mpris.MediaPlayer2.TrackList", "Tracks")
        metadata = bus(track.player, "get-property", "org.mpris.MediaPlayer2.Player", "Metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        current = metadata.get("mpris:trackid")
        if isinstance(ids, list) and current in ids:
            upcoming = ids[ids.index(current) + 1:ids.index(current) + 6]
            result = bus(track.player, "call", "org.mpris.MediaPlayer2.TrackList", "GetTracksMetadata",
                         "ao", str(len(upcoming)), *upcoming) if upcoming else []
            if isinstance(result, list):
                if result and isinstance(result[0], list):
                    result = result[0]
                self.items = [(str(item.get("xesam:title", "Sin título")),
                               ", ".join(item.get("xesam:artist", []))) for item in result]
                self.label = "MPRIS" if upcoming else "Fin de la cola"
                return
        try:
            data = self.api.request("now-playing")
            info = data.get("info", {}) or {}
            # Do not combine a different player's queue with selected MPRIS data.
            if info.get("name") != track.title or info.get("artistName") != track.artist:
                self.items, self.label = [], "La API y MPRIS están cambiando de canción"
                self.api_available = False
                return
            self.now_playing = info
            self.sampled = time.monotonic()
            self.api_available = True
            self.shuffle = bool(info["shuffleMode"]) if "shuffleMode" in info else bool(self.api.request("shuffle-mode")["value"])
            mode = info.get("repeatMode")
            if mode is None:
                mode = self.api.request("repeat-mode")["value"]
            self.repeat = {0: "None", 1: "Track", 2: "Playlist"}.get(mode)
            self.items, self.label = cider_queue(self.api.request("queue"), info)
        except urllib.error.HTTPError as error:
            self.items, self.label = [], "Conecta Cider: amui --connect-cider" if error.code in (401, 403) else "API de Cider no disponible"
            self.api_available = False
        except (OSError, ValueError, KeyError, TypeError):
            self.items, self.label = [], "Cider no expone cola · revisa su API local"
            self.api_available = False

    def run(self):
        while not self.stop.is_set():
            try:
                self.poll(self.player.track)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                self.items, self.label = [], "Respuesta de cola no disponible"
            self.stop.wait(2)


class History:
    def __init__(self, path=None):
        self.path = Path(path) if path else cache_dir() / "history.jsonl"

    def append(self, track, timestamp):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = dict(timestamp=datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                     title=track.title, artist=track.artist, album=track.album)
        with self.path.open("a", encoding="utf-8") as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def recent(self, count):
        try:
            with self.path.open(encoding="utf-8") as file:
                entries = deque(maxlen=count)
                for line in file:
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict) and all(key in value for key in ("timestamp", "title", "artist", "album")):
                            entries.append(value)
                    except ValueError:
                        continue
                return list(reversed(entries))
        except FileNotFoundError:
            return []


def dominant_palette(art, fallback):
    path = urllib.parse.unquote(urllib.parse.urlparse(art).path) if art.startswith("file://") else art
    tool = shutil.which("magick") or shutil.which("convert")
    if not tool or not path or not Path(path).is_file():
        return fallback
    try:
        raw = subprocess.run([tool, path + "[0]", "-resize", "32x32!", "-alpha", "off", "-depth", "8", "rgb:-"],
                             capture_output=True, timeout=3)
        if raw.returncode or len(raw.stdout) != 32 * 32 * 3:
            return fallback
        counts = {}
        for i in range(0, len(raw.stdout), 3):
            c = tuple(raw.stdout[i:i + 3])
            hue, saturation, value = colorsys.rgb_to_hsv(*(v / 255 for v in c))
            if saturation > .25 and value > .2:
                bucket = round(hue * 24) % 24
                counts[bucket] = counts.get(bucket, 0) + 1
        if not counts:
            return fallback
        hue = max(counts, key=counts.get) / 24
        accents = [nearest_color(tuple(round(v * 255) for v in colorsys.hsv_to_rgb((hue + delta) % 1, .52, .98)))
                   for delta in (0, .12, -.12)]
        return (*fallback[:4], *accents)
    except (OSError, subprocess.TimeoutExpired):
        return fallback


def detect_cover(protocol="auto", environ=None):
    env = os.environ if environ is None else environ
    if protocol != "auto":
        return protocol
    if env.get("KITTY_WINDOW_ID") or env.get("TERM") == "xterm-kitty":
        return "kitty"
    if env.get("TERM_PROGRAM", "").lower() in ("iterm.app", "wezterm"):
        return "iterm"
    if env.get("TERM", "").startswith("foot") or "sixel" in env.get("TERM", ""):
        return "sixel"
    return "none"


def inline_image(path, rect, protocol):
    x, y, w, h = rect
    if protocol == "iterm":
        data = Path(path).read_bytes()
        if len(data) > 8_000_000:
            raise ValueError("Portada demasiado grande")
        return (f"\033]1337;File=inline=1;size={len(data)};width={w};height={h};preserveAspectRatio=1:".encode()
                + base64.b64encode(data) + b"\a")
    if protocol == "sixel":
        if shutil.which("chafa"):
            args = ["chafa", "--format=sixels", f"--size={w}x{h}", "--animate=off", path]
        elif shutil.which("magick"):
            args = ["magick", path + "[0]", "-resize", f"{w * 8}x{h * 16}", "sixel:-"]
        else:
            raise ValueError("Sixel necesita chafa o ImageMagick")
        result = subprocess.run(args, capture_output=True, timeout=3)
        if result.returncode:
            raise ValueError("No se pudo generar la portada Sixel")
        return result.stdout
    return b""


def export_lyrics(track, synced, plain, directory):
    directory = Path(directory).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[\x00-\x1f/\\:*?"<>|]', "_", f"{track.artist} - {track.title}").strip(" .")[:120] or "lyrics"
    # Bound UTF-8 byte size as well as Unicode code point count.
    name = name.encode("utf-8")[:180].decode("utf-8", "ignore")
    if synced:
        lines = []
        for seconds, text in synced:
            centis = max(0, round(seconds * 100))
            lines.append(f"[{centis // 6000:02d}:{centis // 100 % 60:02d}.{centis % 100:02d}]{text}")
        suffix = ".lrc"
    elif plain:
        lines, suffix = plain, ".txt"
    else:
        raise ValueError("No hay letras cargadas para exportar")
    for index in range(1000):
        path = directory / (name + (f" ({index})" if index else "") + suffix)
        try:
            with path.open("x", encoding="utf-8") as file:
                file.write("\n".join(lines) + "\n")
            return path
        except FileExistsError:
            continue
    raise ValueError("Demasiados archivos con el mismo nombre")


def signed_lastfm(params, secret):
    signature = "".join(key + str(params[key]) for key in sorted(params)) + secret
    return {**params, "api_sig": hashlib.md5(signature.encode()).hexdigest(), "format": "json"}


class Scrobbler:
    def __init__(self, stop, conf, path=None):
        self.stop = stop
        self.providers = conf["providers"]
        try:
            self.credentials = json.loads(read_secret(conf["credentials_file"]) or "{}")
        except ValueError:
            self.credentials = {}
        if not isinstance(self.credentials, dict):
            self.credentials = {}
        self.credentials.setdefault("listenbrainz", {})
        self.credentials.setdefault("lastfm", {})
        for provider in ("listenbrainz", "lastfm"):
            if not isinstance(self.credentials[provider], dict):
                self.credentials[provider] = {}
        token = os.environ.get("AMUI_LISTENBRAINZ_TOKEN")
        if token:
            self.credentials["listenbrainz"] = {"token": token}
        for key in ("api_key", "secret", "session_key"):
            value = os.environ.get("AMUI_LASTFM_" + key.upper())
            if value:
                self.credentials["lastfm"][key] = value
        self.path = Path(path) if path else cache_dir() / "scrobbles.json"
        try:
            saved = json.loads(self.path.read_text())
            self.pending = [item for item in saved if isinstance(item, dict) and
                            all(key in item for key in ("provider", "timestamp", "title", "artist", "album", "duration"))] if isinstance(saved, list) else []
        except (OSError, ValueError):
            self.pending = []
        self.incoming = queue.Queue()
        self.label = "Scrobbling desactivado" if not self.providers else "Scrobbling listo"
        self.thread = threading.Thread(target=self.run, daemon=True)

    def enqueue(self, track, timestamp):
        for provider in self.providers:
            self.incoming.put(dict(provider=provider, timestamp=int(timestamp), title=track.title,
                                   artist=track.artist, album=track.album, duration=track.length))

    def submit(self, event):
        provider = event["provider"]
        cred = self.credentials.get(provider, {})
        if provider == "listenbrainz":
            if not cred.get("token"):
                raise ValueError("ListenBrainz necesita token")
            data = {"listen_type": "single", "payload": [{"listened_at": event["timestamp"],
                    "track_metadata": {"artist_name": event["artist"], "track_name": event["title"],
                                       "release_name": event["album"]}}]}
            result = json_request("https://api.listenbrainz.org/1/submit-listens", data,
                                  {"Authorization": "Token " + cred["token"]}, timeout=7)
            if result.get("status") != "ok":
                raise ValueError("ListenBrainz no aceptó el scrobble")
        elif provider == "lastfm":
            if any(not cred.get(key) for key in ("api_key", "secret", "session_key")):
                raise ValueError("Last.fm necesita api_key, secret y session_key")
            params = dict(method="track.scrobble", api_key=cred["api_key"], sk=cred["session_key"],
                          artist=event["artist"], track=event["title"], album=event["album"],
                          timestamp=str(event["timestamp"]))
            if event["duration"]:
                params["duration"] = str(round(event["duration"]))
            result = json_request("https://ws.audioscrobbler.com/2.0/", signed_lastfm(params, cred["secret"]),
                                  form=True, timeout=7)
            if result.get("error") or str(result.get("scrobbles", {}).get("@attr", {}).get("accepted")) != "1":
                raise ValueError("Last.fm no aceptó el scrobble; revisa credenciales y fecha")

    def run(self):
        if not self.providers:
            return
        next_retry = 0
        while not self.stop.is_set():
            changed = False
            try:
                while True:
                    item = self.incoming.get_nowait()
                    if item not in self.pending:
                        self.pending.append(item)
                        changed = True
            except queue.Empty:
                pass
            if changed:
                try:
                    atomic_json(self.path, self.pending)
                except OSError:
                    self.label = "No se pudo guardar la cola de scrobbles"
            if time.monotonic() >= next_retry:
                for item in list(self.pending):
                    if item.get("provider") not in self.providers or self.stop.is_set():
                        continue
                    try:
                        self.submit(item)
                        self.pending.remove(item)
                        atomic_json(self.path, self.pending)
                        self.label = "Scrobble enviado · " + item["provider"]
                    except (OSError, ValueError, KeyError, TypeError):
                        self.label = "Scrobble pendiente · revisa conexión / credenciales"
                next_retry = time.monotonic() + 60
            self.stop.wait(.25)
        # The producer may enqueue its last listen while shutdown is starting.
        while not self.incoming.empty():
            item = self.incoming.get_nowait()
            if item not in self.pending:
                self.pending.append(item)
        try:
            atomic_json(self.path, self.pending)
        except OSError:
            self.label = "No se pudo guardar la cola de scrobbles"


class Activity:
    """Count time actually listened, not seek distance or paused time."""
    def __init__(self, stop, player, config, palette):
        self.stop, self.player, self.config = stop, player, config
        self.history = History()
        self.scrobbler = Scrobbler(stop, config["scrobble"])
        self.identity = ""
        self.previous = None
        self.last_tick = None
        self.listened = 0.
        self.started = 0
        self.submitted = False
        self.notice = ""
        self.palette = palette
        self.art = ""
        self.thread = threading.Thread(target=self.run, daemon=True)

    def observe(self, track, now=None, wall=None):
        now = time.monotonic() if now is None else now
        wall = time.time() if wall is None else wall
        prev = self.previous
        repeat = bool(prev and track.identity == self.identity and prev.length > 30 and
                      prev.position >= prev.length - 3 and track.position < 3)
        if track.title and track.status == "Playing" and (track.identity != self.identity or repeat):
            self.identity, self.listened, self.started, self.submitted = track.identity, 0., wall, False
            if self.config["history"]:
                try:
                    self.history.append(track, wall)
                except OSError:
                    self.notice = "No se pudo guardar el historial"
        elif prev and track.identity == self.identity and track.status == prev.status == "Playing" and self.last_tick is not None:
            delta = now - self.last_tick
            moved = track.position - prev.position
            if 0 <= delta <= 2 and -1 <= moved <= delta + 2:
                self.listened += delta
        threshold = min(track.length / 2, 240) if track.length > 0 else 240
        if track.identity == self.identity and (track.length == 0 or track.length > 30) and self.listened >= threshold and not self.submitted:
            self.scrobbler.enqueue(track, self.started)
            self.submitted = True
        self.previous, self.last_tick = track, now

    def run(self):
        while not self.stop.is_set():
            track = self.player.track
            self.observe(track)
            if self.config["dynamic_palette"] and (track.identity, track.art) != self.art:
                self.art = (track.identity, track.art)
                self.palette = dominant_palette(track.art, self.palette)
            self.stop.wait(.25)


def smooth(current, target, delta):
    return current + (target - current) * (1 - math.exp(-max(0, delta) * 16))
