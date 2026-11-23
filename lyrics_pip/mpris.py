from dataclasses import dataclass

BUS_PREFIX = "org.mpris.MediaPlayer2.firefox"
OBJ_PATH = "/org/mpris/MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
PROPS_IFACE = "org.freedesktop.DBus.Properties"


@dataclass
class Track:
    title: str
    artist: str
    album: str
    length: float


@dataclass
class PlayerState:
    track: "Track | None"
    position: float
    playing: bool


def parse_metadata(meta: dict):
    title = meta.get("xesam:title") or ""
    if not title:
        return None
    artists = meta.get("xesam:artist") or []
    if isinstance(artists, str):
        artists = [artists]
    length = meta.get("mpris:length") or 0
    return Track(
        title=title,
        artist=", ".join(artists),
        album=meta.get("xesam:album") or "",
        length=float(length) / 1_000_000,
    )


class MprisReader:
    """Reads the state of a Firefox MPRIS player over the session bus."""

    def __init__(self):
        self._bus = None
        self._name = None
        self._names = []

    def _get_bus(self):
        from gi.repository import Gio

        if self._bus is None:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return self._bus

    def _call(self, name, iface, method, params, reply_type):
        from gi.repository import Gio

        return self._get_bus().call_sync(
            name, OBJ_PATH, iface, method, params,
            reply_type, Gio.DBusCallFlags.NONE, 500, None,
        )

    def _prop(self, name, prop):
        from gi.repository import GLib

        res = self._call(
            name, PROPS_IFACE, "Get",
            GLib.Variant("(ss)", (PLAYER_IFACE, prop)),
            GLib.VariantType("(v)"),
        )
        return res.unpack()[0]

    def _firefox_names(self):
        from gi.repository import GLib

        res = self._call(
            "org.freedesktop.DBus", "org.freedesktop.DBus", "ListNames",
            None, GLib.VariantType("(as)"),
        )
        return [n for n in res.unpack()[0] if n.startswith(BUS_PREFIX)]

    def _all_props(self, name):
        from gi.repository import GLib

        res = self._call(
            name, PROPS_IFACE, "GetAll",
            GLib.Variant("(s)", (PLAYER_IFACE,)),
            GLib.VariantType("(a{sv})"),
        )
        return res.unpack()[0]

    def _state(self, props):
        track = parse_metadata(props.get("Metadata") or {})
        position = (props.get("Position") or 0) / 1_000_000
        return PlayerState(track, position, props.get("PlaybackStatus") == "Playing")

    def read(self):
        """Return PlayerState, or None if no player / any D-Bus error."""
        try:
            # Fast path: one GetAll call on the cached bus name.
            if self._name is not None:
                try:
                    props = self._all_props(self._name)
                    if props.get("PlaybackStatus") == "Playing" or len(self._names) < 2:
                        return self._state(props)
                except Exception:
                    self._name = None
            # Slow path: (re)discover Firefox players, prefer the one playing.
            self._names = self._firefox_names()
            best = None
            for name in self._names:
                try:
                    props = self._all_props(name)
                except Exception:
                    continue
                if best is None or props.get("PlaybackStatus") == "Playing":
                    best = (name, props)
                if props.get("PlaybackStatus") == "Playing":
                    break
            if best is None:
                self._name = None
                return None
            self._name = best[0]
            return self._state(best[1])
        except Exception:
            self._bus = None
            self._name = None
            return None
