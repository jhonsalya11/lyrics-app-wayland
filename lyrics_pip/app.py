import os
import signal
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from .clock import PositionEstimator
from .instance import acquire_single_instance
from .lrc import active_index
from .custom import CUSTOM_DIR, read_custom_text, resolve_lyrics, save_custom
from .lyrics import NETWORK_ERROR, clean_title, forget_cached
from .mpris import MprisReader
from .syncer import SyncSession, format_timestamp
from .ui import LyricsWindow, ask_lyrics_text, layer_shell_available, load_config

CACHE_DIR = Path.home() / ".cache" / "lyrics-pip-wayland"
FAST_MS = 250
SLOW_MS = 1000
IDLE_MS = 2000
MAX_MISSES = 3
RETRY_MS = 20000

MSG_IDLE = "Tidak ada lagu diputar"
MSG_SEARCHING = "Mencari lirik..."
MSG_NOT_FOUND = "Lirik tidak ditemukan"
MSG_RETRY = "Gagal memuat lirik, mencoba lagi..."
MSG_SAVE_FAILED = "Gagal menyimpan lirik"
MSG_SYNC_ABORTED = "Sinkron dibatalkan: lagu berganti"
MSG_SYNC_SAVED = "Sinkron tersimpan: {title}"


class App:
    def __init__(self):
        self.win = LyricsWindow()
        self.reader = MprisReader()
        self.estimator = PositionEstimator()
        self.track_key = None
        self.token = 0
        self.lyrics = None
        self.current = None
        self.sync = None
        self._interval = FAST_MS
        self._timer = 0
        self._misses = 0

        self.win.on_edit = self._edit
        self.win.on_reload = self._reload
        self.win.on_sync = self._sync_start
        self.win.connect("destroy", lambda *_: Gtk.main_quit())
        self.win.set_status(MSG_IDLE)
        self.win.show_all()
        self._schedule(FAST_MS)

    # ---- polling -------------------------------------------------------
    def _schedule(self, ms: int) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
        self._interval = ms
        self._timer = GLib.timeout_add(ms, self._tick)

    def _tick(self) -> bool:
        try:
            wanted = self._poll()
        except Exception:
            wanted = IDLE_MS
        if wanted != self._interval:
            self._schedule(wanted)
            return False
        return True

    def _poll(self) -> int:
        state = self.reader.read()
        if state is None or state.track is None:
            if self.sync is not None:
                return FAST_MS  # never lose a tap-sync session to an MPRIS hiccup
            # Tolerate brief MPRIS hiccups (e.g. Firefox stalled under memory
            # pressure): only give up after several consecutive misses.
            self._misses += 1
            if self.track_key is None:
                return IDLE_MS
            if self._misses >= MAX_MISSES:
                self._reset(MSG_IDLE)
                return IDLE_MS
            return FAST_MS
        self._misses = 0

        track = state.track
        key = (track.title, track.artist, round(track.length))
        if key != self.track_key:
            if self._same_song_during_sync(track):
                # Only the reported duration changed: keep the session, follow the new key.
                self.track_key, self.current = key, track
            else:
                self._start_fetch(key, track)

        # Keep the estimator current even for plain lyrics: tap-sync reads it on click.
        pos = self.estimator.update(state.position, time.monotonic(), state.playing)
        if self.lyrics is not None and self.lyrics.synced:
            self.win.set_active(active_index(self.lyrics.lines, pos))
        return FAST_MS if state.playing else SLOW_MS

    def _reset(self, message: str) -> None:
        self.token += 1
        self.track_key = None
        self.current = None
        self.lyrics = None
        self._sync_abort()
        self.win.set_song_controls(False)
        self.win.set_sync_button_visible(False)
        self.win.set_status(message)

    # ---- fetching ------------------------------------------------------
    def _start_fetch(self, key, track) -> None:
        note = self._sync_leave_for_new_song()
        self.token += 1
        token = self.token
        self.track_key = key
        self.current = track
        self.lyrics = None
        self.estimator = PositionEstimator()
        self.win.set_song_controls(True)
        self.win.set_sync_button_visible(False)
        self.win.set_status(f"{note}\n{MSG_SEARCHING}" if note else MSG_SEARCHING)

        def work():
            result = resolve_lyrics(
                clean_title(track.title, track.artist), track.artist, track.album,
                track.length, CACHE_DIR, CUSTOM_DIR,
            )
            GLib.idle_add(self._deliver, token, result, track)

        threading.Thread(target=work, daemon=True).start()

    def _deliver(self, token, result, track) -> bool:
        if token != self.token:  # song changed while downloading: drop it
            return False
        self.win.set_sync_button_visible(
            result is not None and result is not NETWORK_ERROR and not result.synced
        )
        if result is NETWORK_ERROR:
            self.lyrics = None
            self.win.set_status(MSG_RETRY)
            GLib.timeout_add(RETRY_MS, self._retry, token, self.track_key, track)
            return False
        self.lyrics = result
        if result is None:
            self.win.set_status(MSG_NOT_FOUND, action=("Tambah lirik", self._edit))
        else:
            self.win.set_lyrics(result, track.title, track.artist)
        return False


    def _edit(self) -> None:
        track, key = self.current, self.track_key
        if track is None:
            return
        title = clean_title(track.title, track.artist)
        heading = f"{track.title} — {track.artist}" if track.artist else track.title
        initial = read_custom_text(title, track.artist, CUSTOM_DIR)
        while True:
            text = ask_lyrics_text(self.win, heading, initial)
            if text is None:
                return
            try:
                save_custom(title, track.artist, text, CUSTOM_DIR)
                break
            except OSError as e:
                # Keep what the user pasted and leave the lyrics view alone.
                heading = f"{MSG_SAVE_FAILED}: {e.strerror or e}\n{track.title}"
                initial = text
        if self.track_key == key:  # song may have changed while the dialog was open
            self._start_fetch(key, track)

    def _reload(self) -> None:
        track = self.current
        if track is None:
            return
        forget_cached(
            clean_title(track.title, track.artist), track.artist, track.length, CACHE_DIR
        )
        self._start_fetch(self.track_key, track)

    # ---- tap-sync --------------------------------------------------------
    def _current_position(self):
        """Live playback position (estimated), or None if no song / song changed."""
        state = self.reader.read()
        if state is None or state.track is None:
            return None
        t, cur = state.track, self.current
        if cur is None or (t.title, t.artist) != (cur.title, cur.artist):
            return None
        return self.estimator.update(state.position, time.monotonic(), state.playing)

    def _sync_refresh(self, message: str = "", bad=None) -> None:
        s = self.sync
        self.win.set_sync_state(s.next_index(), s.done(), s.total(), message, bad)

    def _sync_start(self) -> None:
        lyrics = self.lyrics
        if self.sync is not None or self.current is None or lyrics is None or lyrics.synced:
            return
        session = SyncSession([text for _, text in lyrics.lines])
        if session.total() == 0:
            return
        self.sync = session
        self.win.enter_sync_mode(
            session.texts, self._sync_mark, self._sync_mark_next,
            self._sync_save, self._sync_cancel,
        )
        self._sync_refresh()

    def _sync_mark(self, index: int) -> None:
        if self.sync is None:
            return
        position = self._current_position()
        if position is None:
            self._sync_refresh(MSG_IDLE)
            return
        stamp = self.sync.mark(index, position, load_config()["sync_offset"])
        self.win.set_sync_row(index, format_timestamp(stamp))
        self._sync_refresh()

    def _sync_mark_next(self) -> None:
        if self.sync is None:
            return
        index = self.sync.next_index()
        if index is not None:
            self._sync_mark(index)

    def _sync_save(self) -> None:
        session = self.sync
        if session is None:
            return
        if not session.is_complete():
            self._sync_refresh("Tandai semua baris dulu")
            return
        bad = session.first_out_of_order()
        if bad is not None:
            self._sync_refresh(f"Urutan waktu tidak naik pada baris {bad + 1}", bad)
            return
        track, key = self.current, self.track_key
        try:
            save_custom(clean_title(track.title, track.artist), track.artist,
                        session.to_lrc(), CUSTOM_DIR)
        except OSError as e:
            self._sync_refresh(f"{MSG_SAVE_FAILED}: {e.strerror or e}")
            return
        self.sync = None
        self.win.exit_sync_mode()
        if self.track_key == key:
            self._start_fetch(key, track)

    def _sync_cancel(self) -> None:
        if not self._sync_abort():
            return
        if self.lyrics is not None and self.current is not None:
            self.win.set_lyrics(self.lyrics, self.current.title, self.current.artist)

    def _same_song_during_sync(self, track) -> bool:
        cur = self.current
        return (self.sync is not None and cur is not None
                and (track.title, track.artist) == (cur.title, cur.artist))

    def _sync_leave_for_new_song(self) -> str:
        """The song changed mid-session. A complete, ordered session is saved for the
        old song (the usual end of a session: the song ends before Simpan); anything else
        is discarded. Returns a short note for the status line, or '' if no session."""
        session, track = self.sync, self.current
        if session is None:
            return ""
        saved = False
        if track is not None and session.is_complete() and session.first_out_of_order() is None:
            try:
                save_custom(clean_title(track.title, track.artist), track.artist,
                            session.to_lrc(), CUSTOM_DIR)
                saved = True
            except OSError:
                pass
        self._sync_abort()
        return MSG_SYNC_SAVED.format(title=track.title) if saved else MSG_SYNC_ABORTED

    def _sync_abort(self) -> bool:
        """Leave sync mode, discarding stamps. True if a session was active."""
        if self.sync is None:
            return False
        self.sync = None
        self.win.exit_sync_mode()
        return True

    def _retry(self, token, key, track) -> bool:
        if token == self.token and key == self.track_key:  # same song still playing
            self._start_fetch(key, track)
        return False


def main() -> None:
    lock = acquire_single_instance(CACHE_DIR / "instance.lock")
    if lock is None:
        return  # already running; keep the single window
    if os.environ.get("WAYLAND_DISPLAY") and not layer_shell_available():
        print("lyrics-pip: gtk-layer-shell tidak tersedia, jendela tidak bisa selalu di atas.\n"
              "  Pasang: sudo apt install gir1.2-gtklayershell-0.1", file=sys.stderr)
    app = App()

    def quit_cleanly():
        app.win.close()  # runs delete-event, which saves window position/size/opacity
        return False

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, quit_cleanly)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, quit_cleanly)
    Gtk.main()
    lock.close()


if __name__ == "__main__":
    main()
