import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lyrics_pip import app as appmod
from lyrics_pip.lyrics import NETWORK_ERROR, Lyrics
from lyrics_pip.mpris import PlayerState, Track
from lyrics_pip.ui import is_visible_position

TRACK = Track("T", "A", "Al", 200.0)
KEY = ("T", "A", 200)


class FakeReader:
    def __init__(self):
        self.result = None

    def read(self):
        return self.result


class FakeWin:
    def __init__(self):
        self.statuses = []
        self.actions = []
        self.controls = []
        self.sync_buttons = []
        self.sync_texts = None
        self.entered = 0
        self.rows = []
        self.sync_states = []
        self.exits = 0
        self.lyrics_shown = []

    def set_status(self, text, action=None):
        self.statuses.append(text)
        self.actions.append(action)

    def set_song_controls(self, visible):
        self.controls.append(visible)

    # --- sync mode recording ---
    def set_sync_button_visible(self, v):
        self.sync_buttons.append(v)

    def enter_sync_mode(self, texts, on_mark, on_mark_next, on_save, on_cancel):
        self.sync_texts = list(texts)
        self.entered += 1

    def set_sync_row(self, i, text):
        self.rows.append((i, text))

    def set_sync_state(self, next_index, done, total, message="", bad_index=None):
        self.sync_states.append(
            {"next": next_index, "done": done, "total": total, "message": message, "bad": bad_index}
        )

    def exit_sync_mode(self):
        self.exits += 1

    def set_lyrics(self, *a):
        self.statuses.append("lyrics")
        self.lyrics_shown.append(a)

    def set_active(self, i):
        pass


def make_app():
    a = appmod.App.__new__(appmod.App)
    a.win, a.reader = FakeWin(), FakeReader()
    a.track_key, a.token, a.lyrics = KEY, 1, None
    a.current = TRACK
    a.sync = None
    a._interval, a._timer, a._misses = appmod.FAST_MS, 0, 0
    a.estimator = appmod.PositionEstimator()
    return a


class PollToleranceTest(unittest.TestCase):
    def test_brief_mpris_failures_keep_current_song(self):
        a = make_app()
        a.reader.result = None
        a._poll()
        a._poll()
        self.assertEqual(a.track_key, KEY)
        self.assertEqual(a.win.statuses, [])

    def test_third_consecutive_failure_resets_to_idle(self):
        a = make_app()
        for _ in range(3):
            a._poll()
        self.assertIsNone(a.track_key)
        self.assertEqual(a.win.statuses, [appmod.MSG_IDLE])

    def test_success_resets_failure_count(self):
        a = make_app()
        a._poll()
        a._poll()
        a.reader.result = PlayerState(TRACK, 5.0, True)
        a._poll()
        a.reader.result = None
        a._poll()
        a._poll()
        self.assertEqual(a.track_key, KEY)


class NetworkRetryTest(unittest.TestCase):
    def test_network_error_shows_retry_message_and_schedules_retry(self):
        a = make_app()
        with mock.patch.object(appmod.GLib, "timeout_add") as ta:
            a._deliver(1, NETWORK_ERROR, TRACK)
        self.assertEqual(a.win.statuses, [appmod.MSG_RETRY])
        self.assertEqual(ta.call_args[0][0], appmod.RETRY_MS)

    def test_retry_refetches_only_if_song_unchanged(self):
        a = make_app()
        with mock.patch.object(a, "_start_fetch", create=True) as sf:
            a._retry(1, KEY, TRACK)
            sf.assert_called_once_with(KEY, TRACK)
        a.token = 2  # song changed
        with mock.patch.object(a, "_start_fetch", create=True) as sf:
            a._retry(1, KEY, TRACK)
            sf.assert_not_called()


class EditAndReloadTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.a = make_app()
        p = mock.patch.object(appmod, "CUSTOM_DIR", self.dir)
        p.start()
        self.addCleanup(p.stop)
        sf = mock.patch.object(self.a, "_start_fetch", create=True)
        self.sf = sf.start()
        self.addCleanup(sf.stop)

    def test_not_found_offers_add_lyrics_action(self):
        self.a._deliver(1, None, TRACK)
        self.assertEqual(self.a.win.statuses, [appmod.MSG_NOT_FOUND])
        self.assertEqual(self.a.win.actions[-1], ("Tambah lirik", self.a._edit))

    def test_edit_saves_and_refetches(self):
        with mock.patch.object(appmod, "ask_lyrics_text", return_value="[00:01.00]hi"):
            self.a._edit()
        self.assertTrue((self.dir / "A - T.lrc").exists())
        self.sf.assert_called_once_with(KEY, TRACK)

    def test_edit_dialog_is_prefilled_with_existing_custom_text(self):
        (self.dir / "A - T.txt").write_text("lama\n", encoding="utf-8")
        with mock.patch.object(appmod, "ask_lyrics_text", return_value=None) as ask:
            self.a._edit()
        self.assertEqual(ask.call_args[0][2], "lama")

    def test_edit_cancel_changes_nothing(self):
        with mock.patch.object(appmod, "ask_lyrics_text", return_value=None):
            self.a._edit()
        self.assertEqual(list(self.dir.iterdir()), [])
        self.sf.assert_not_called()

    def test_edit_empty_text_removes_custom_and_refetches(self):
        (self.dir / "A - T.txt").write_text("lama\n", encoding="utf-8")
        with mock.patch.object(appmod, "ask_lyrics_text", return_value=""):
            self.a._edit()
        self.assertEqual(list(self.dir.iterdir()), [])
        self.sf.assert_called_once_with(KEY, TRACK)

    def test_edit_when_song_changed_during_dialog_saves_original_without_refetch(self):
        def ask(*_a):
            self.a.track_key = ("Lain", "B", 100)
            self.a.current = Track("Lain", "B", "", 100.0)
            return "teks"

        with mock.patch.object(appmod, "ask_lyrics_text", side_effect=ask):
            self.a._edit()
        self.assertTrue((self.dir / "A - T.txt").exists())
        self.sf.assert_not_called()

    def test_edit_save_failure_reopens_dialog_with_text_and_keeps_lyrics(self):
        with mock.patch.object(appmod, "ask_lyrics_text", side_effect=["pasted", None]) as ask, \
                mock.patch.object(appmod, "save_custom", side_effect=OSError("disk")):
            self.a._edit()
        self.assertEqual(ask.call_count, 2)
        heading, initial = ask.call_args[0][1], ask.call_args[0][2]
        self.assertIn(appmod.MSG_SAVE_FAILED, heading)
        self.assertEqual(initial, "pasted")
        self.assertEqual(self.a.win.statuses, [])  # lyrics view untouched
        self.sf.assert_not_called()

    def test_edit_save_failure_then_success_refetches_once(self):
        with mock.patch.object(appmod, "ask_lyrics_text", side_effect=["x", "x"]), \
                mock.patch.object(appmod, "save_custom", side_effect=[OSError("disk"), None]):
            self.a._edit()
        self.sf.assert_called_once_with(KEY, TRACK)

    def test_edit_without_song_is_noop(self):
        self.a.current = None
        with mock.patch.object(appmod, "ask_lyrics_text") as ask:
            self.a._edit()
        ask.assert_not_called()

    def test_reload_forgets_cache_and_refetches(self):
        with mock.patch.object(appmod, "forget_cached") as forget:
            self.a._reload()
        forget.assert_called_once_with(
            appmod.clean_title(TRACK.title, TRACK.artist), TRACK.artist,
            TRACK.length, appmod.CACHE_DIR,
        )
        self.sf.assert_called_once_with(KEY, TRACK)

    def test_reload_without_song_is_noop(self):
        self.a.current = None
        with mock.patch.object(appmod, "forget_cached") as forget:
            self.a._reload()
        forget.assert_not_called()
        self.sf.assert_not_called()


class ControlsTest(unittest.TestCase):
    def test_controls_follow_song_state(self):
        a = make_app()
        a.track_key, a.current = None, None
        a.reader.result = PlayerState(TRACK, 5.0, True)
        with mock.patch.object(appmod.threading, "Thread"):
            a._poll()
        self.assertEqual(a.win.controls, [True])
        a.reader.result = None
        for _ in range(3):
            a._poll()
        self.assertEqual(a.win.controls, [True, False])


class TapSyncTest(unittest.TestCase):
    PLAIN = Lyrics([(0.0, "a"), (0.0, ""), (0.0, "b")], False)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.a = make_app()
        self.a.lyrics = self.PLAIN
        for patcher in (
            mock.patch.object(appmod, "CUSTOM_DIR", self.dir),
            mock.patch.object(appmod, "load_config", return_value={"sync_offset": 0.3}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        sf = mock.patch.object(self.a, "_start_fetch", create=True)
        self.sf = sf.start()
        self.addCleanup(sf.stop)

    def start(self):
        self.a._sync_start()
        return self.a.sync

    def test_sync_button_only_for_plain_lyrics(self):
        self.a._deliver(1, Lyrics([(0.0, "a")], False), TRACK)
        self.assertIs(self.a.win.sync_buttons[-1], True)
        self.a._deliver(1, Lyrics([(1.0, "a")], True), TRACK)
        self.assertIs(self.a.win.sync_buttons[-1], False)
        self.a._deliver(1, None, TRACK)
        self.assertIs(self.a.win.sync_buttons[-1], False)

    def test_start_fetch_hides_sync_button(self):
        b = make_app()
        with mock.patch.object(appmod.threading, "Thread"):
            b._start_fetch(KEY, TRACK)
        self.assertIs(b.win.sync_buttons[-1], False)

    def test_sync_start_only_with_plain_lyrics_that_have_text(self):
        for lyrics in (None, Lyrics([(1.0, "a")], True), Lyrics([(0.0, ""), (0.0, "  ")], False)):
            self.a.lyrics = lyrics
            self.a._sync_start()
            self.assertEqual(self.a.win.entered, 0)
            self.assertIsNone(self.a.sync)
        self.a.lyrics = self.PLAIN
        self.a._sync_start()
        self.assertEqual(self.a.win.entered, 1)
        self.assertEqual(self.a.win.sync_texts, ["a", "b"])
        self.assertIsNotNone(self.a.sync)

    def test_mark_uses_live_position_minus_offset(self):
        s = self.start()
        self.a.reader.result = PlayerState(TRACK, 12.0, True)
        self.a._sync_mark(0)
        self.assertAlmostEqual(s.stamps[0], 12.2, places=3)
        self.assertEqual(self.a.win.rows[-1], (0, "[00:12.20]"))

    def test_poll_keeps_estimator_current_even_for_plain_lyrics(self):
        s = self.start()
        self.a.reader.result = PlayerState(TRACK, 10.0, True)
        self.a._poll()
        self.a.reader.result = PlayerState(TRACK, 11.0, True)
        self.a._poll()
        self.a._sync_mark(0)
        self.assertAlmostEqual(s.stamps[0], 10.7, places=1)  # not 11.2

    def test_mark_without_song_makes_no_stamp_and_shows_message(self):
        s = self.start()
        self.a.reader.result = None
        self.a._sync_mark(0)
        self.a._sync_mark_next()
        self.assertEqual(s.stamps, [None, None])
        self.assertEqual(self.a.win.sync_states[-1]["message"], appmod.MSG_IDLE)

    def test_space_marks_next_in_order(self):
        s = self.start()
        self.a.reader.result = PlayerState(TRACK, 5.0, True)
        self.a._sync_mark_next()
        self.a._sync_mark_next()
        self.assertEqual([x is not None for x in s.stamps], [True, True])
        before = list(s.stamps)
        self.a._sync_mark_next()
        self.assertEqual(s.stamps, before)

    def test_save_rejects_incomplete_and_out_of_order(self):
        s = self.start()
        self.a._sync_save()
        self.assertEqual(list(self.dir.iterdir()), [])
        self.assertTrue(self.a.win.sync_states[-1]["message"])
        s.stamps = [10.0, 5.0]
        self.a._sync_save()
        self.assertEqual(list(self.dir.iterdir()), [])
        self.assertEqual(self.a.win.sync_states[-1]["bad"], 1)
        self.assertIsNotNone(self.a.sync)

    def test_save_writes_lrc_exits_and_refetches(self):
        s = self.start()
        s.stamps = [10.0, 12.0]
        self.a._sync_save()
        self.assertEqual(
            (self.dir / "A - T.lrc").read_text(encoding="utf-8").strip(),
            "[00:10.00]a\n[00:12.00]b",
        )
        self.assertEqual(self.a.win.exits, 1)
        self.assertIsNone(self.a.sync)
        self.sf.assert_called_once_with(KEY, TRACK)

    def test_save_failure_keeps_session(self):
        s = self.start()
        s.stamps = [10.0, 12.0]
        with mock.patch.object(appmod, "save_custom", side_effect=OSError("disk")):
            self.a._sync_save()
        self.assertIs(self.a.sync, s)
        self.assertEqual(self.a.win.exits, 0)
        self.assertTrue(self.a.win.sync_states[-1]["message"])
        self.sf.assert_not_called()

    def test_cancel_restores_lyrics_without_saving(self):
        self.start()
        self.a._sync_cancel()
        self.assertEqual(self.a.win.exits, 1)
        self.assertIsNone(self.a.sync)
        self.assertEqual(self.a.win.lyrics_shown[-1][0], self.PLAIN)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_track_change_during_sync_aborts(self):
        self.start()
        b = self.a
        with mock.patch.object(appmod.threading, "Thread"):
            appmod.App._start_fetch(b, ("Lain", "B", 100), Track("Lain", "B", "", 100.0))
        self.assertEqual(b.win.exits, 1)
        self.assertIsNone(b.sync)
        self.assertIn(appmod.MSG_SYNC_ABORTED, b.win.statuses[-1])

    def test_track_change_with_complete_ordered_session_saves_for_old_song(self):
        s = self.start()
        s.stamps = [10.0, 12.0]
        with mock.patch.object(appmod.threading, "Thread"):
            appmod.App._start_fetch(self.a, ("Lain", "B", 100), Track("Lain", "B", "", 100.0))
        self.assertEqual(
            (self.dir / "A - T.lrc").read_text(encoding="utf-8").strip(),
            "[00:10.00]a\n[00:12.00]b",
        )
        self.assertIsNone(self.a.sync)
        self.assertEqual(self.a.win.exits, 1)
        self.assertIn("Sinkron tersimpan", self.a.win.statuses[-1])

    def test_track_change_with_out_of_order_session_discards(self):
        s = self.start()
        s.stamps = [10.0, 5.0]
        with mock.patch.object(appmod.threading, "Thread"):
            appmod.App._start_fetch(self.a, ("Lain", "B", 100), Track("Lain", "B", "", 100.0))
        self.assertEqual(list(self.dir.iterdir()), [])
        self.assertIn(appmod.MSG_SYNC_ABORTED, self.a.win.statuses[-1])

    def test_transient_mpris_loss_keeps_sync_session(self):
        s = self.start()
        self.a.reader.result = None
        for _ in range(appmod.MAX_MISSES + 3):
            self.a._poll()
        self.assertIs(self.a.sync, s)
        self.assertEqual(self.a.win.exits, 0)
        self.assertNotIn(appmod.MSG_IDLE, self.a.win.statuses)

    def test_length_update_during_sync_does_not_refetch_or_block_marking(self):
        s = self.start()
        longer = Track("T", "A", "Al", 201.0)
        self.a.reader.result = PlayerState(longer, 7.0, True)
        self.a._poll()
        self.sf.assert_not_called()
        self.assertIs(self.a.sync, s)
        self.assertEqual(self.a.track_key, ("T", "A", 201))
        self.a._sync_mark(0)
        self.assertIsNotNone(s.stamps[0])


class VisiblePositionTest(unittest.TestCase):
    MON = [(0, 0, 1920, 1080)]

    def test_visible(self):
        self.assertTrue(is_visible_position(100, 100, 380, 300, self.MON))

    def test_offscreen_after_monitor_unplugged(self):
        self.assertFalse(is_visible_position(2690, 373, 380, 300, self.MON))

    def test_second_monitor_present(self):
        mons = self.MON + [(1920, 0, 1920, 1080)]
        self.assertTrue(is_visible_position(2690, 373, 380, 300, mons))

    def test_barely_on_screen_is_not_visible(self):
        self.assertFalse(is_visible_position(1900, 100, 380, 300, self.MON))


if __name__ == "__main__":
    unittest.main()
