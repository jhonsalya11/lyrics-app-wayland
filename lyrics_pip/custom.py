import re
import urllib.request
from pathlib import Path

from .lrc import parse_lrc
from .lyrics import Lyrics, fetch_lyrics

CUSTOM_DIR = Path(__file__).resolve().parent.parent / "lyrics"
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_NAME = 150


def _clean_part(text: str) -> str:
    return _UNSAFE.sub("_", text or "").lstrip(". ").strip()


def safe_filename(artist: str, title: str) -> str:
    a, t = _clean_part(artist), _clean_part(title)
    name = f"{a} - {t}" if a and t else (a or t)
    # Cap by encoded bytes: filesystems limit names to 255 bytes, not characters.
    name = name.encode("utf-8")[:_MAX_NAME].decode("utf-8", "ignore").rstrip()
    return name or "untitled"


def _paths(title, artist, directory):
    base = Path(directory) / safe_filename(artist, title)
    return base.with_name(base.name + ".lrc"), base.with_name(base.name + ".txt")


def _read(path: Path):
    try:
        return path.read_text(encoding="utf-8-sig")  # tolerate a BOM
    except (OSError, UnicodeDecodeError):
        return None


def _is_lrc(text: str) -> bool:
    """LRC only if most non-blank lines carry a timestamp (one '[2:30] solo' stays plain)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    timed = sum(1 for ln in lines if parse_lrc(ln))
    return bool(lines) and timed * 2 >= len(lines)


def _plain(text: str):
    lines = text.replace("\r\n", "\n").strip().splitlines()
    return [(0.0, ln.strip()) for ln in lines]


def load_custom(title: str, artist: str, directory) -> "Lyrics | None":
    lrc, txt = _paths(title, artist, directory)
    for path in (lrc, txt):
        text = _read(path)
        if text is None or not text.strip():
            continue
        if _is_lrc(text):
            return Lyrics(parse_lrc(text), True)
        return Lyrics(_plain(text), False)
    return None


def read_custom_text(title: str, artist: str, directory) -> str:
    lrc, txt = _paths(title, artist, directory)
    for path in (lrc, txt):
        text = _read(path)
        if text is not None:
            return text.replace("\r\n", "\n").strip()  # same normalisation as save_custom
    return ""


def save_custom(title: str, artist: str, text: str, directory) -> "Path | None":
    """Save pasted lyrics; empty text deletes this song's custom file. May raise OSError."""
    lrc, txt = _paths(title, artist, directory)
    text = (text or "").lstrip("\ufeff").replace("\r\n", "\n").strip()
    if not text:
        lrc.unlink(missing_ok=True)
        txt.unlink(missing_ok=True)
        return None
    target, other = (lrc, txt) if _is_lrc(text) else (txt, lrc)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text + "\n", encoding="utf-8")
    other.unlink(missing_ok=True)
    return target


def resolve_lyrics(title, artist, album, duration, cache_dir, custom_dir,
                   opener=urllib.request.urlopen):
    """Custom file first (it always wins), then cache/LRCLIB."""
    custom = load_custom(title, artist, custom_dir)
    if custom is not None:
        return custom
    return fetch_lyrics(title, artist, album, duration, cache_dir, opener=opener)
