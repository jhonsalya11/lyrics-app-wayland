import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .lrc import parse_lrc

API = "https://lrclib.net/api/get"
SEARCH_API = "https://lrclib.net/api/search"
TIMEOUT = 8
NOT_FOUND_TTL = 3600

_SUFFIX = re.compile(
    r"\s*[\(\[]\s*("
    r"official\b[^\)\]]*|lyrics?\b[^\)\]]*|audio\b[^\)\]]*|video\b[^\)\]]*"
    r"|mv|music video|\d+k|hd|hq|\d{3,4}p"
    r")[\)\]]\s*$",
    re.IGNORECASE,
)


@dataclass
class Lyrics:
    lines: list
    synced: bool


def clean_title(title: str, artist: str = "") -> str:
    """Strip video/audio decorations and, if it matches `artist`, a leading 'Artist - '."""
    prev = None
    while prev != title:
        prev = title
        title = _SUFFIX.sub("", title)
    title = title.strip()
    if artist:
        head, sep, rest = title.partition(" - ")
        if sep and rest.strip() and head.strip().casefold() == artist.strip().casefold():
            title = rest.strip()
    return title


def _cache_path(cache_dir: Path, title, artist, duration) -> Path:
    key = f"{title}|{artist}|{round(duration)}".encode()
    return Path(cache_dir) / (hashlib.sha1(key).hexdigest() + ".json")


def _read_cache(path: Path):
    """Return ('hit', Lyrics) / ('miss', None) / (None, None) when no usable entry."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None, None
    if data.get("not_found"):
        if time.time() - data.get("ts", 0) < NOT_FOUND_TTL:
            return "miss", None
        return None, None
    try:
        return "hit", Lyrics([tuple(x) for x in data["lines"]], bool(data["synced"]))
    except (KeyError, TypeError):
        return None, None


def _write_cache(path: Path, obj) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj))
    except OSError:
        pass


class _NetworkError:
    def __repr__(self):
        return "NETWORK_ERROR"


NETWORK_ERROR = _NetworkError()


def _to_lyrics(data):
    """Lyrics from one LRCLIB record, or None if it holds no lyrics."""
    if not isinstance(data, dict):
        return None
    synced = parse_lrc(data.get("syncedLyrics") or "")
    if synced:
        return Lyrics(synced, True)
    plain = [(0.0, ln) for ln in (data.get("plainLyrics") or "").splitlines()]
    if any(t for _, t in plain):
        return Lyrics(plain, False)
    return None


def _pick_closest(records, duration):
    best = None
    for rec in records:
        lyr = _to_lyrics(rec)
        if lyr is None:
            continue
        gap = abs(float(rec.get("duration") or 0) - duration) if duration else 0
        key = (not lyr.synced, gap)
        if best is None or key < best[0]:
            best = (key, lyr)
    return best[1] if best else None


def fetch_lyrics(title, artist, album, duration, cache_dir,
                 opener=urllib.request.urlopen):
    """Fetch lyrics from cache or LRCLIB.

    Returns Lyrics, None (not found / unusable query) or NETWORK_ERROR (could not
    reach LRCLIB; nothing cached). Never raises.
    """
    try:
        path = _cache_path(cache_dir, title, artist, duration)
        state, cached = _read_cache(path)
        if state == "hit":
            return cached
        if state == "miss":
            return None

        base = {"track_name": title, "artist_name": artist}
        if duration and duration > 0:
            base["duration"] = int(round(duration))

        def request(url):
            req = urllib.request.Request(url, headers={"User-Agent": "lyrics-pip/0.1"})
            with opener(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))

        urls = []
        if album:
            urls.append(API + "?" + urllib.parse.urlencode({**base, "album_name": album}))
        urls.append(API + "?" + urllib.parse.urlencode(base))
        search_params = {"track_name": title, "artist_name": artist}
        urls.append(SEARCH_API + "?" + urllib.parse.urlencode(search_params))

        for i, url in enumerate(urls):
            is_search = i == len(urls) - 1
            try:
                data = request(url)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                return None  # e.g. 400 for an unusable query: don't cache
            except (urllib.error.URLError, OSError):
                return NETWORK_ERROR
            except ValueError:
                return None
            if is_search:
                result = _pick_closest(data, duration) if isinstance(data, list) else None
            else:
                result = _to_lyrics(data)
            if result is not None:
                _write_cache(path, {"lines": result.lines, "synced": result.synced})
                return result

        _write_cache(path, {"not_found": True, "ts": time.time()})
        return None
    except Exception:
        return None


def forget_cached(title: str, artist: str, duration: float, cache_dir) -> None:
    """Drop the cached result (lyrics or 'not found' marker) for one song."""
    try:
        _cache_path(cache_dir, title, artist, duration).unlink(missing_ok=True)
    except OSError:
        pass
