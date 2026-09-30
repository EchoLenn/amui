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
    "lyrics": ["L"], "focus": ["f"], "visualizer": ["v"], "theme": ["t"], "theme_picker": ["T"],
    "scroll_up": ["["], "scroll_down": ["]"], "offset_back": [","], "offset_forward": ["."],
    "retry": ["R"], "open": ["o"], "search": ["/"], "export": ["S"], "queue": ["Q"], "music": ["b"],
    "favorite": ["H"], "library": ["A"], "sleep": ["Z"],
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
                    lyrics=True, cava=True, queue=True, history=True, notifications=True, desktop_notifications=False,
                    animations=True, dynamic_palette=False, palette_light=False, mouse=True, cover_protocol="auto",
                    theme_source="auto", palette_mode="extract", pywal_file=str(Path(os.environ.get("XDG_CACHE_HOME", str(Path.home()/".cache"))) / "wal/colors.json"),
                    export_dir=str(Path.home() / "Music/amui-lyrics"))
    allowed = set(defaults) | {"keybinds", "themes", "cider", "scrobble"}
    if set(data) - allowed:
        raise ValueError("Opciones desconocidas: " + ", ".join(sorted(set(data) - allowed)))
    conf = {**defaults, **data}
    if conf["theme_source"] == "auto":
        conf["theme_source"] = "cover" if conf["dynamic_palette"] else "fixed"
    if conf["theme_source"] not in ("cover", "fixed", "custom", "pywal"):
        raise ValueError("theme_source: cover, fixed, custom o pywal")
    if conf["palette_mode"] not in ("extract", "complementary", "contrast"):
        raise ValueError("palette_mode: extract, complementary o contrast")
    for key, default in defaults.items():
        if isinstance(default, bool) and not isinstance(conf[key], bool):
            raise ValueError(f"{key} debe ser true o false")
        if isinstance(default, str) and not isinstance(conf[key], str):
            raise ValueError(f"{key} debe ser texto")
    conf["dynamic_palette"] = conf["theme_source"] == "cover"
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


def appearance_signature(config_path):
    try:
        return hashlib.sha256(Path(config_path).read_bytes()).hexdigest()
    except FileNotFoundError:
        return "missing"


def restore_appearance(conf, config_path, available=None):
    """A manually edited TOML takes precedence over a previously saved selection."""
    try:
        saved = json.loads(Path(config_path).with_suffix(".appearance.json").read_text())
        if saved.get("config_signature") != appearance_signature(config_path):
            return
        if saved.get("theme_source") not in ("cover", "fixed", "custom", "pywal") or saved.get("palette_mode") not in ("extract", "complementary", "contrast"):
            return
        if not isinstance(saved.get("theme"), str):
            return
        if available is not None and saved["theme"] not in available:
            return
        for key in ("theme_source", "palette_mode", "theme"):
            conf[key] = saved[key]
        conf["dynamic_palette"] = conf["theme_source"] == "cover"
    except (OSError, ValueError, AttributeError):
        pass


def save_appearance(conf, theme, config_path):
    atomic_json(Path(config_path).with_suffix(".appearance.json"), dict(
        config_signature=appearance_signature(config_path), theme=theme,
        theme_source=conf["theme_source"], palette_mode=conf["palette_mode"]))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def json_request(url, payload=None, headers=None, form=False, timeout=3):
    body = None if payload is None else (urllib.parse.urlencode(payload).encode() if form
                                        else json.dumps(payload).encode())
    hdr = {"User-Agent": "amui/0.5", "Accept": "application/json", **(headers or {})}
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

    def music(self, path):
        if not path.startswith(("/v1/catalog/", "/v1/me/")) or ".." in path:
            raise ValueError("Ruta de música no válida")
        token = os.environ.get("AMUI_CIDER_TOKEN") or read_secret(self.token_file)
        result = json_request(self.url + "/api/v1/amapi/run-v3", {"path": path},
                              {"apptoken": token} if token else {}, timeout=10)
        if not isinstance(result, dict) or result.get("errors") or result.get("status") == "error":
            raise ValueError("Cider no pudo consultar Apple Music")
        data = result.get("data", result)
        if not isinstance(data, dict) or data.get("errors"):
            raise ValueError("Apple Music no devolvió datos válidos")
        return data

    def message(self, kind, data):
        token = os.environ.get("AMUI_CIDER_TOKEN") or read_secret(self.token_file)
        result = json_request(self.url + "/api/v1/messages/message", {"type": kind, "data": data},
                              {"apptoken": token} if token else {})
        if not isinstance(result, dict) or result.get("status") != "success":
            raise ValueError("Cider rechazó el mensaje")


class MusicBrowser:
    """Serial background requests; stale searches cannot replace newer results."""
    def __init__(self, stop, conf):
        self.stop, self.api = stop, CiderAPI(conf["cider"])
        self.jobs = queue.Queue()
        self.generation = 0
        self.items, self.next_path = [], ""
        self.label, self.busy = "Escribe una búsqueda o abre Biblioteca", False
        self.storefront = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def search(self, term="", library=False, kind="songs", next_path=""):
        if next_path and self.busy:
            return
        self.generation += 1
        previous = list(self.items) if next_path else []
        self.items, self.next_path = previous, ""
        self.label, self.busy = "Buscando…", True
        self.jobs.put((self.generation, "search", (term, library, kind, next_path, previous)))

    def tracks(self, item, next_path=""):
        if self.busy:
            return
        self.generation += 1
        previous = list(self.items) if next_path else []
        self.items, self.next_path = previous, ""
        self.label, self.busy = "Cargando canciones…", True
        self.jobs.put((self.generation, "tracks", (dict(item), next_path, previous)))

    def snapshot(self):
        return (list(self.items), self.next_path, self.label)

    def restore(self, snapshot):
        # Invalidate an outstanding collection request when navigating back.
        self.generation += 1
        self.items, self.next_path, self.label = snapshot
        self.busy = False

    def region(self):
        if not self.storefront:
            stores = self.api.music("/v1/me/storefront").get("data", [])
            if not stores or not re.fullmatch("[a-z]{2}", str(stores[0].get("id", ""))):
                raise ValueError("No se pudo obtener la región de Apple Music")
            self.storefront = stores[0]["id"]
        return self.storefront

    def lookup_tracks(self, item, next_path=""):
        kind, ident = item.get("type"), str(item.get("id", ""))
        if kind not in ("albums", "playlists", "library-albums", "library-playlists") or not re.fullmatch(r"[\w.:-]+", ident, re.ASCII):
            raise ValueError("Colección no válida")
        library = kind.startswith("library-")
        base = "/v1/me/library" if library else f"/v1/catalog/{self.region()}"
        path = next_path or f"{base}/{kind.removeprefix('library-')}/{ident}/tracks?limit=25"
        items, more = self.parse_items(self.api.music(path), "library-songs" if library else "songs")
        return [item for item in items if item["type"] in ("songs", "library-songs")], more

    def choose(self, item, action="play-item"):
        if self.busy:
            return
        if action not in ("play-item", "play-later", "play-next"):
            raise ValueError("Acción de reproducción no válida")
        if item.get("type") not in ("songs", "albums", "playlists", "library-songs", "library-albums", "library-playlists") or not re.fullmatch(r"[\w.:-]+", str(item.get("id", "")), re.ASCII):
            raise ValueError("Elemento de música no válido")
        self.busy, self.label = True, "Enviando a Cider…"
        self.jobs.put((self.generation, action, dict(item)))

    def lookup(self, term, library, kind, next_path):
        if kind not in ("songs", "albums", "playlists"):
            raise ValueError("Tipo de música no válido")
        resource = ("library-" if library else "") + kind
        if next_path:
            path = next_path
        elif library:
            path = "/v1/me/library/" + ("search?" + urllib.parse.urlencode({"term":term, "types":resource, "limit":25})
                                          if term else kind + "?limit=25")
        else:
            if not term.strip():
                return [], ""
            path = f"/v1/catalog/{self.region()}/search?" + urllib.parse.urlencode({"term":term, "types":kind, "limit":25})
        data = self.api.music(path)
        return self.parse_items(data, resource)

    @staticmethod
    def parse_items(data, resource):
        section = data.get("results", {}).get(resource, {}) if "results" in data else data
        if not isinstance(section, dict) or not isinstance(section.get("data", []), list):
            raise ValueError("Lista de música no válida")
        rows = section.get("data", [])
        items = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            attrs = row.get("attributes", {})
            if not isinstance(attrs, dict):
                continue
            item_type = row.get("type", resource)
            if re.fullmatch(r"[\w.:-]+", str(row.get("id", "")), re.ASCII) and item_type in ("songs", "albums", "playlists", "library-songs", "library-albums", "library-playlists"):
                items.append(dict(id=str(row["id"]), type=item_type, title=str(attrs.get("name") or "Sin título"),
                                  artist=str(attrs.get("artistName") or attrs.get("curatorName") or ""), album=str(attrs.get("albumName") or "")))
        next_page = section.get("next", "")
        if not isinstance(next_page, str) or not next_page.startswith(("/v1/catalog/", "/v1/me/")):
            next_page = ""
        return items, next_page

    def run(self):
        while not self.stop.is_set():
            try:
                generation, action, args = self.jobs.get(timeout=.2)
            except queue.Empty:
                continue
            if self.stop.is_set():
                break
            if action in ("search", "tracks") and generation != self.generation:
                continue
            try:
                if action in ("search", "tracks"):
                    items, next_path = self.lookup(*args[:4]) if action == "search" else self.lookup_tracks(*args[:2])
                    if generation == self.generation:
                        previous = args[4] if action == "search" else args[2]
                        seen = {(item["type"], item["id"]) for item in previous}
                        # Repeated songs in a playlist are intentional; retain order.
                        combined = previous + (items if action == "tracks" else [item for item in items if (item.get("type"), item.get("id")) not in seen])
                        self.items, self.next_path = combined, next_path
                        self.label = f"{len(combined)} resultados" if combined else "Sin resultados · / buscar · Tab biblioteca"
                        if action == "tracks":
                            self.label = f"{len(combined)} canciones · P reproducir colección" if combined else "Sin canciones disponibles · Esc volver"
                else:
                    result = self.api.request(action, {"type":args["type"], "id":args["id"]})
                    if not isinstance(result, dict) or result.get("status") != "ok" or result.get("errors"):
                        raise ValueError("Cider rechazó la selección")
                    if generation == self.generation:
                        self.label = ("Reproducción solicitada: " if action == "play-item" else "Añadido a cola: ") + args["title"]
            except urllib.error.HTTPError as error:
                if generation == self.generation:
                    self.label = "Conecta Cider: amui --connect-cider" if error.code in (401, 403) else f"Cider no disponible (HTTP {error.code})"
            except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
                if generation == self.generation:
                    self.label = "No se pudo consultar Cider; revisa conexión y suscripción"
            except Exception:
                if generation == self.generation:
                    self.label = "Respuesta inesperada de Cider; vuelve a buscar"
            finally:
                if generation == self.generation:
                    if action == "tracks" and self.label.startswith(("No se pudo", "Cider no disponible", "Conecta Cider", "Respuesta inesperada")):
                        self.next_path = args[1]
                        self.label += " · r reintentar · Esc volver"
                    self.busy = False


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


def is_cider_player(player):
    """Only recover metadata for a local Chromium instance owned by Cider."""
    match = re.fullmatch(r"chromium\.instance(\d+)", player)
    if not match:
        return False
    try:
        return Path(f"/proc/{match[1]}/exe").resolve(strict=True).name.lower() == "cider"
    except OSError:
        return False


def cider_artwork(info):
    """Cache official artwork for the MPRIS-empty recovery path."""
    artwork = info.get("artwork") or {}
    url = artwork.get("url", "") if isinstance(artwork, dict) else ""
    url = url.replace("{w}", "600").replace("{h}", "600").replace("{f}", "jpg")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".mzstatic.com"):
        return ""
    path = cache_dir() / "artwork" / (hashlib.sha256(url.encode()).hexdigest()+".img")
    if path.is_file():
        return str(path)
    temporary = None
    try:
        with urllib.request.build_opener(NoRedirect).open(url, timeout=2) as response:
            data = response.read(4_000_001)
        if not data or len(data) > 4_000_000:
            return ""
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
        temporary.replace(path)
        return str(path)
    except (OSError, ValueError):
        return ""
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def queue_items(data):
    rows = data if isinstance(data, list) else data.get("items", data.get("queue", [])) if isinstance(data, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) or
            not isinstance(row.get("attributes", row), dict) for row in rows):
        raise ValueError("Formato de cola no reconocido")
    return rows


def queue_signature(data):
    rows = queue_items(data)
    return tuple((str(row.get("id", "")), str(row.get("type", "")),
                  str(row.get("attributes", row).get("name", "")),
                  str(row.get("attributes", row).get("artistName", ""))) for row in rows)


def cider_queue(data, current, detailed=False):
    """Exclude history/current; don't invent an index for ambiguous duplicates."""
    try:
        items = queue_items(data)
    except ValueError:
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
    if type(index) is not int or not -1 <= index < len(items):
        return [], "Posición de cola no disponible"
    result = []
    for position, item in enumerate(items[index + 1:], index + 1):
        attr = item.get("attributes", item)
        labels = (str(attr.get("name", "Sin título")), str(attr.get("artistName", "")))
        result.append((position, *labels) if detailed else labels)
    return result, "Cider API" if result else "Fin de la cola"


class Extras:
    def __init__(self, stop, player, config):
        self.stop, self.player = stop, player
        self.api = CiderAPI(config["cider"])
        self.items, self.label = [], "Consultando cola…"
        self.shuffle, self.repeat = None, None
        self.volume = None
        self.lock = threading.RLock()
        self.identity = ""
        self.now_playing = {}
        self.sampled = 0
        self.api_available = False
        self.queue_view = None
        self.favorite, self.library = None, None
        self.library_identity = ""
        self.library_at = 0
        self.storefront = ""
        self.thread = threading.Thread(target=self.run, daemon=True)

    def poll(self, track):
        with self.lock:
            self._poll(track)

    def _poll(self, track):
        if track.identity != self.identity:
            self.queue_view = None
            self.items, self.label = [], "Actualizando cola…"
            self.api_available = False
            self.favorite, self.library = None, None
            self.library_identity = ""
        self.identity = track.identity
        if not track.player:
            self.queue_view = None
            self.items, self.label = [], "Abre Cider para ver la cola"
            self.shuffle, self.repeat, self.now_playing = None, None, {}
            self.volume = None
            self.api_available = False
            self.favorite, self.library = None, None
            self.library_identity = ""
            return
        shuffle = bus(track.player, "get-property", "org.mpris.MediaPlayer2.Player", "Shuffle")
        repeat = bus(track.player, "get-property", "org.mpris.MediaPlayer2.Player", "LoopStatus")
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
                self.queue_view = None
                self.shuffle, self.repeat = shuffle, repeat
                self.api_available = False
                return
        try:
            data = self.api.request("now-playing")
            if not isinstance(data, dict):
                raise ValueError("Respuesta de Cider no válida")
            info = data.get("info", {}) or {}
            if not isinstance(info, dict):
                raise ValueError("Metadatos de Cider no válidos")
            unloaded = not track.title and not info.get("name") and is_cider_player(track.player)
            # Do not combine a different player's queue with selected MPRIS data.
            if not unloaded and (info.get("name") != track.title or info.get("artistName") != track.artist):
                self.queue_view = None
                self.items, self.label = [], "La API y MPRIS están cambiando de canción"
                self.api_available = False
                return
            self.now_playing = {} if unloaded else info
            self.sampled = time.monotonic()
            self.api_available = True
            try:
                volume = self.api.request("volume")["volume"]
                if not isinstance(volume, bool) and isinstance(volume, (int, float)) and 0 <= volume <= 1:
                    self.volume = volume
            except (OSError, ValueError, KeyError, TypeError):
                pass
            try:
                mode = info.get("shuffleMode")
                if type(mode) not in (bool, int) or mode not in (0, 1):
                    mode = self.api.request("shuffle-mode")["value"]
                if type(mode) in (bool, int) and mode in (0, 1):
                    self.shuffle = bool(mode)
            except (OSError, ValueError, KeyError, TypeError):
                pass
            try:
                mode = info.get("repeatMode")
                if type(mode) is not int or mode not in (0, 1, 2):
                    mode = self.api.request("repeat-mode")["value"]
                if type(mode) is int and mode in (0, 1, 2):
                    self.repeat = {0: "None", 1: "Track", 2: "Playlist"}[mode]
            except (OSError, ValueError, KeyError, TypeError):
                pass
            if unloaded:
                self.queue_view = None
                self.items, self.label = [], "Cider sin canción cargada · b para elegir música"
                self.favorite, self.library, self.library_identity = None, None, ""
                return
            self._library_state(info, track)
            data = self.api.request("queue")
            self._publish_queue(data, info, track)
        except urllib.error.HTTPError as error:
            self.items, self.label = [], "Conecta Cider: amui --connect-cider" if error.code in (401, 403) else "API de Cider no disponible"
            self.api_available = False
        except (OSError, ValueError, KeyError, TypeError):
            self.items, self.label = [], "Cider no expone cola · revisa su API local"
            self.api_available = False
        # Do not publish temporary MPRIS defaults while the API is in flight.
        if not self.api_available:
            self.queue_view = None
            if self.shuffle is None:
                self.shuffle = shuffle
            if self.repeat is None:
                self.repeat = repeat

    def _resource(self, info):
        params = info.get("playParams") or {}
        if not isinstance(params, dict):
            raise ValueError("La canción no tiene identificador de Apple Music")
        ident = str(params.get("catalogId") or params.get("id") or info.get("id") or "")
        kind = params.get("kind", "song")
        kind = {"song": "songs", "musicVideo": "music-videos", "songs": "songs", "music-videos": "music-videos"}.get(kind)
        if not kind or not re.fullmatch(r"[A-Za-z0-9._-]+", ident):
            raise ValueError("Este elemento no admite favoritos o biblioteca")
        if ident.startswith("i."):
            return f"/v1/me/library/{kind}/{ident}", "library-" + kind, ident
        if not self.storefront:
            resources = self.api.music("/v1/me/storefront").get("data", [])
            if not resources or not isinstance(resources[0], dict):
                raise ValueError("No se pudo consultar la región de Apple Music")
            self.storefront = str(resources[0].get("id", ""))
            if not re.fullmatch(r"[a-z]{2}", self.storefront):
                raise ValueError("Región de Apple Music no válida")
        return f"/v1/catalog/{self.storefront}/{kind}/{ident}", kind, ident

    def _confirmed_library_state(self, info, track):
        path, kind, ident = self._resource(info)
        resources = self.api.music(path + "?extend=inFavorites&fields=inFavorites,inLibrary,playParams").get("data", [])
        if not resources or not isinstance(resources[0], dict) or str(resources[0].get("id")) != ident:
            raise ValueError("Apple Music no confirmó la canción consultada")
        attributes = resources[0].get("attributes", {})
        self.favorite = attributes.get("inFavorites") if type(attributes.get("inFavorites")) is bool else None
        self.library = True if kind.startswith("library-") else (
            attributes.get("inLibrary") if type(attributes.get("inLibrary")) is bool else None)
        self.library_identity, self.library_at = track.identity, time.monotonic() + 10
        return kind, ident

    def _library_state(self, info, track):
        # Cider's now-playing fields may be optimistic; verify the saved resource.
        if self.library_identity == track.identity and time.monotonic() < self.library_at:
            return
        try:
            self._confirmed_library_state(info, track)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            self.favorite, self.library = None, None
            self.library_identity, self.library_at = track.identity, time.monotonic() + 10

    def library_action(self, track, action):
        """Change the requested current song and publish only server-confirmed state."""
        with self.lock:
            if action not in ("favorite", "add"):
                raise ValueError("Acción de biblioteca desconocida")
            if not track.identity or track.identity != self.player.track.identity:
                return "La canción cambió; vuelve a intentar"
            info = self._queue_current(track)
            kind, ident = self._confirmed_library_state(info, track)
            if action == "favorite" and self.favorite is None:
                return "Apple Music no confirmó el estado de favorito"
            if action == "add" and self.library is True:
                return "Esta canción ya está en tu biblioteca"
            desired = not self.favorite if action == "favorite" else True
            self._queue_current(track, info)
            if action == "favorite":
                # A tiny supported Cider plugin bridges the real favorites API.
                # The legacy set-rating endpoint is not equivalent to favorites.
                self.api.message("amui:favorite", dict(id=ident, type=kind, state=desired,
                                 request=f"{os.getpid()}:{time.monotonic_ns()}"))
            else:
                result = self.api.request("add-to-library", {})
                if not isinstance(result, dict) or result.get("status") != "ok":
                    raise ValueError("Cider rechazó añadir a biblioteca")
            for attempt in range(6):
                self._queue_current(track, info)
                self._confirmed_library_state(info, track)
                value = self.favorite if action == "favorite" else self.library
                if value is desired:
                    if action == "add":
                        return "Canción añadida a tu biblioteca"
                    return "Favorito añadido" if desired else "Favorito retirado"
                if self.stop.wait(.15):
                    break
            if action == "favorite":
                return "Cider no confirmó el favorito · activa el complemento amui"
            return "Añadir a biblioteca solicitado; esperando confirmación"

    def _queue_current(self, track, expected=None):
        if track.identity != self.player.track.identity:
            raise ValueError("La canción cambió; vuelve a seleccionar en Q")
        info = self.api.request("now-playing").get("info", {})
        if info.get("name") != track.title or info.get("artistName") != track.artist:
            raise ValueError("Cider está cambiando de canción; vuelve a seleccionar")
        if expected is not None and info.get("playParams") != expected.get("playParams"):
            raise ValueError("La canción cambió; vuelve a seleccionar")
        return info

    def _publish_queue(self, data, info, track):
        rows, self.label = cider_queue(data, info, detailed=True)
        self.items = [(title, artist) for _, title, artist in rows]
        self.queue_view = (track.identity, tuple(rows), queue_signature(data))

    def jump_queue(self, view, selection):
        return self.queue_action(view, selection, "jump")

    def queue_action(self, view, selection, action):
        """Revalidate the visible queue before acting on its absolute indexes."""
        with self.lock:
            if action not in ("jump", "delete", "clear_pending"):
                raise ValueError("Acción de cola desconocida")
            if not view or view[0] != self.player.track.identity or (action != "clear_pending" and
                    (type(selection) is not int or not 0 <= selection < len(view[1]))):
                return "La canción cambió; vuelve a seleccionar en Q"
            track = self.player.track
            info = self._queue_current(track)
            data = self.api.request("queue")
            rows, _ = cider_queue(data, info, detailed=True)
            if queue_signature(data) != view[2] or tuple(rows) != view[1]:
                return "La cola cambió; vuelve a seleccionar en Q"
            if action == "jump":
                result = self.api.request("queue/change-to-index", {"index": rows[selection][0]})
                if not isinstance(result, dict) or result.get("status") != "ok":
                    raise ValueError("Cider rechazó el salto")
                return "Salto solicitado a la canción seleccionada"
            if not rows:
                return "No quedan canciones pendientes"
            indexes = [rows[selection][0]] if action == "delete" else [row[0] for row in reversed(rows)]
            # Cider's removeFromQueue uses _queueItems.splice(index, 1): zero based.
            # Descending deletion preserves history/current and avoids shifted indexes.
            signature = queue_signature(data)
            for index in indexes:
                self._queue_current(track, info)
                data = self.api.request("queue")
                if queue_signature(data) != signature:
                    self._publish_queue(data, info, track)
                    return "La cola cambió; se detuvo la eliminación"
                expected = signature[:index] + signature[index + 1:]
                result = self.api.request("queue/remove-by-index", {"index": index})
                if not isinstance(result, dict) or result.get("status") != "ok":
                    raise ValueError("Cider rechazó la eliminación")
                # HTTP acknowledges dispatch before the renderer updates its queue.
                for attempt in range(6):
                    self._queue_current(track, info)
                    data = self.api.request("queue")
                    observed = queue_signature(data)
                    if observed == expected:
                        break
                    if observed != signature or self.stop.wait(.05):
                        break
                self._publish_queue(data, info, track)
                if observed != expected:
                    return "La cola cambió o Cider no confirmó la eliminación"
                signature = expected
            return "Canción eliminada de la cola" if action == "delete" else "Cola pendiente vaciada"

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


def contrast(a, b):
    def luminance(c):
        values = [v / 3294.6 if v <= 10 else ((v / 255 + .055) / 1.055) ** 2.4 for v in c]
        return sum(v * weight for v, weight in zip(values, (.2126, .7152, .0722)))
    x, y = sorted((luminance(a), luminance(b)))
    return (y + .05) / (x + .05)


def readable(color, background, minimum=4.5):
    candidates = [i for i in range(16, 256) if contrast(rgb(i), rgb(background)) >= minimum]
    return min(candidates, key=lambda i: sum((a-b)**2 for a, b in zip(rgb(i), color)))


def cluster_colors(pixels, k=5):
    """Deterministic farthest-point initialization and bounded Lloyd iterations."""
    centers = [pixels[0]]
    for _ in range(k - 1):
        candidate = max(pixels, key=lambda p: min(sum((a-b)**2 for a, b in zip(p, c)) for c in centers))
        if candidate in centers:
            break
        centers.append(candidate)
    for _ in range(12):
        groups = [[] for _ in centers]
        for p in pixels:
            i = min(range(len(centers)), key=lambda i: sum((a-b)**2 for a, b in zip(p, centers[i])))
            groups[i].append(p)
        updated = [tuple(round(sum(p[j] for p in group)/len(group)) for j in range(3)) if group else c
                   for group, c in zip(groups, centers)]
        if updated == centers:
            break
        centers = updated
    return [c for _, c in sorted(zip(map(len, groups), centers), reverse=True)]


def pywal_palette(path):
    try:
        data = json.loads(Path(path).expanduser().read_text())
        special, colors = data["special"], data["colors"]
        values = [special["background"], special["foreground"], colors["color8"], colors["color0"],
                  colors["color1"], colors["color4"], colors["color5"]]
        palette = tuple(parse_color(value) for value in values)
        return (palette[0], *(readable(rgb(c), palette[0], 3 if i == 3 else 4.5) for i, c in enumerate(palette[1:], 1)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError("Pywal: genera colors.json con wal o revisa pywal_file") from error


def custom_palette(path):
    try:
        values = json.loads(Path(path).read_text())
        return tuple(parse_color(values[key]) for key in COLOR_NAMES)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError("Tema personalizado no válido") from error


def dominant_palette(art, fallback, light=False, mode="extract"):
    path = urllib.parse.unquote(urllib.parse.urlparse(art).path) if art.startswith("file://") else art
    tool = shutil.which("magick") or shutil.which("convert")
    if not tool or not path or not Path(path).is_file():
        return fallback
    try:
        signature = hashlib.sha256(Path(path).read_bytes()).hexdigest() + (":light" if light else ":dark") + ":" + mode
        cache = cache_dir() / "palettes.json"
        try:
            saved = json.loads(cache.read_text())
            if not isinstance(saved, dict):
                saved = {}
        except (OSError, ValueError):
            saved = {}
        cached = saved.get(signature)
        if isinstance(cached, list) and len(cached) == 7 and all(type(i) is int and 16 <= i <= 255 for i in cached):
            return tuple(cached)
        raw = subprocess.run([tool, path + "[0]", "-resize", "32x32!", "-alpha", "off", "-depth", "8", "rgb:-"],
                             capture_output=True, timeout=3)
        if raw.returncode or len(raw.stdout) != 32 * 32 * 3:
            return fallback
        clusters = cluster_colors([tuple(raw.stdout[i:i+3]) for i in range(0, len(raw.stdout), 3)])
        dominant = clusters[0]
        bright = light and sum(dominant) / 3 > 160
        bg = nearest_color(tuple(round(220 + v * .1) if bright else round(v * .09 + 9) for v in dominant))
        fg = readable((24, 24, 30) if bright else (242, 242, 246), bg, 7)
        muted = readable((115, 115, 130), bg)
        border = readable(tuple(round(v * .5 + 50) for v in dominant), bg, 3)
        accents = [readable(c, bg) for c in clusters[:3]]
        while len(accents) < 3:
            hue, sat, _ = colorsys.rgb_to_hsv(*(v / 255 for v in dominant))
            c = tuple(round(v * 255) for v in colorsys.hsv_to_rgb((hue + .12 * len(accents)) % 1, max(.35, sat), .9))
            accents.append(readable(c, bg))
        if mode in ("complementary", "contrast"):
            hue, saturation, _ = colorsys.rgb_to_hsv(*(v/255 for v in dominant))
            offsets = (0, .5, .08) if mode == "complementary" else (0, 1/3, 2/3)
            accents = [readable(tuple(round(v*255) for v in colorsys.hsv_to_rgb((hue+offset)%1,
                        max(.65, saturation), .85 if bright else 1)), bg, 7 if mode == "contrast" else 4.5) for offset in offsets]
        palette = (bg, fg, muted, border, *accents)
        saved[signature] = palette
        try:
            atomic_json(cache, dict(list(saved.items())[-256:]))
        except OSError:
            pass
        return palette
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
        commands = []
        if shutil.which("chafa"):
            commands.append(["chafa", "--format=sixels", f"--size={w}x{h}", "--animate=off", path])
        if shutil.which("magick"):
            commands.append(["magick", path + "[0]", "-resize", f"{w * 8}x{h * 16}", "sixel:-"])
        if not commands:
            raise ValueError("Sixel necesita chafa o ImageMagick")
        for args in commands:
            try:
                result = subprocess.run(args, capture_output=True, timeout=3)
                if not result.returncode and result.stdout:
                    return result.stdout
            except (OSError, subprocess.TimeoutExpired):
                continue
        raise ValueError("No se pudo generar la portada Sixel")
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
            path = urllib.parse.unquote(urllib.parse.urlparse(track.art).path) if track.art.startswith("file://") else track.art
            try:
                stat = Path(path).stat()
                stamp = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                stamp = None
            signature = (track.identity, track.art, stamp, self.config["palette_light"], self.config["palette_mode"])
            if self.config["dynamic_palette"] and signature != self.art:
                self.art = signature
                self.palette = dominant_palette(track.art, self.palette, self.config["palette_light"], self.config["palette_mode"])
            self.stop.wait(.25)


def smooth(current, target, delta):
    return current + (target - current) * (1 - math.exp(-max(0, delta) * 16))
