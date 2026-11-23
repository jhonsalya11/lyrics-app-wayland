import json
import tempfile
import unittest
from pathlib import Path

from lyrics_pip.custom import (
    load_custom, read_custom_text, resolve_lyrics, safe_filename, save_custom,
)
from lyrics_pip.lyrics import Lyrics


class SafeFilenameTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(safe_filename("Alesana", "Song"), "Alesana - Song")
        self.assertEqual(safe_filename("", "Song"), "Song")

    def test_replaces_unsafe_chars(self):
        self.assertEqual(safe_filename("AC/DC", "Back In Black"), "AC_DC - Back In Black")
        self.assertEqual(safe_filename("A", "Why?: yes"), "A - Why__ yes")

    def test_never_escapes_or_hides(self):
        name = safe_filename("..", "../x")
        self.assertNotIn("/", name)
        self.assertFalse(name.startswith("."))
        self.assertEqual(safe_filename("", ""), "untitled")
        self.assertLessEqual(len(safe_filename("a" * 300, "b" * 300)), 150)


class CustomStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "lyrics"

    def test_plain_text_roundtrip_and_crlf(self):
        path = save_custom("Judul", "Artis", "a\r\n\r\nb\r\n", self.dir)
        self.assertEqual(path.name, "Artis - Judul.txt")
        self.assertEqual(
            load_custom("Judul", "Artis", self.dir),
            Lyrics([(0.0, "a"), (0.0, ""), (0.0, "b")], False),
        )

    def test_lrc_text_is_synced(self):
        path = save_custom("Judul", "Artis", "[00:01.00]hi", self.dir)
        self.assertEqual(path.name, "Artis - Judul.lrc")
        self.assertEqual(load_custom("Judul", "Artis", self.dir), Lyrics([(1.0, "hi")], True))

    def test_saving_other_kind_removes_old_file(self):
        save_custom("J", "A", "teks biasa", self.dir)
        save_custom("J", "A", "[00:01.00]x", self.dir)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["A - J.lrc"])
        save_custom("J", "A", "teks biasa lagi", self.dir)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["A - J.txt"])

    def test_lrc_file_without_timestamps_is_plain(self):
        self.dir.mkdir(parents=True)
        (self.dir / "A - J.lrc").write_text("satu\ndua", encoding="utf-8")
        self.assertEqual(load_custom("J", "A", self.dir), Lyrics([(0.0, "satu"), (0.0, "dua")], False))

    def test_save_empty_deletes_and_returns_none(self):
        save_custom("J", "A", "x", self.dir)
        self.assertIsNone(save_custom("J", "A", "  \n", self.dir))
        self.assertIsNone(load_custom("J", "A", self.dir))
        self.assertIsNone(save_custom("Lain", "A", "", self.dir))  # nothing to delete

    def test_empty_save_only_touches_that_song(self):
        save_custom("J", "A", "x", self.dir)
        save_custom("K", "A", "y", self.dir)
        save_custom("J", "A", "", self.dir)
        self.assertIsNotNone(load_custom("K", "A", self.dir))

    def test_never_escapes_directory(self):
        path = save_custom("../x", "..", "teks", self.dir)
        self.assertEqual(path.parent, self.dir)

    def test_unreadable_or_non_utf8_is_ignored(self):
        self.dir.mkdir(parents=True)
        (self.dir / "A - J.txt").write_bytes(b"\xff\xfe\x00")
        self.assertIsNone(load_custom("J", "A", self.dir))
        self.assertEqual(read_custom_text("J", "A", self.dir), "")

    def test_read_custom_text(self):
        self.assertEqual(read_custom_text("J", "A", self.dir), "")
        save_custom("J", "A", "[00:01.00]hi", self.dir)
        self.assertEqual(read_custom_text("J", "A", self.dir), "[00:01.00]hi")


class ReviewFixesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "lyrics"

    def test_one_timestamp_like_line_keeps_plain_text_plain(self):
        path = save_custom("J", "A", "a\nb\n[2:30] guitar solo\nc", self.dir)
        self.assertEqual(path.suffix, ".txt")
        res = load_custom("J", "A", self.dir)
        self.assertFalse(res.synced)
        self.assertEqual([t for _, t in res.lines], ["a", "b", "[2:30] guitar solo", "c"])

    def test_mostly_timestamped_text_is_lrc(self):
        save_custom("J", "A", "[00:01.00]a\n[00:02.00]b\nuntimed", self.dir)
        res = load_custom("J", "A", self.dir)
        self.assertTrue(res.synced)
        self.assertEqual(res.lines, [(1.0, "a"), (2.0, "b")])

    def test_indented_lrc_lines_are_kept(self):
        save_custom("J", "A", "[00:01.00]a\n  [00:02.00]b\n\t[00:03.00]c", self.dir)
        res = load_custom("J", "A", self.dir)
        self.assertEqual(res.lines, [(1.0, "a"), (2.0, "b"), (3.0, "c")])

    def test_bom_is_ignored(self):
        self.dir.mkdir(parents=True)
        (self.dir / "A - J.lrc").write_bytes(b"\xef\xbb\xbf[00:01.00]first\n[00:02.00]second")
        self.assertEqual(load_custom("J", "A", self.dir).lines, [(1.0, "first"), (2.0, "second")])
        (self.dir / "A - K.txt").write_bytes(b"\xef\xbb\xbfsatu\ndua")
        self.assertEqual(load_custom("K", "A", self.dir).lines[0], (0.0, "satu"))
        save_custom("L", "A", "\ufeff[00:01.00]x", self.dir)
        self.assertEqual(load_custom("L", "A", self.dir).lines, [(1.0, "x")])

    def test_long_cjk_names_fit_the_filesystem(self):
        path = save_custom("あ" * 100, "い" * 100, "teks", self.dir)
        self.assertIsNotNone(path)
        self.assertLessEqual(len(path.name.encode("utf-8")), 255)


class Opener:
    def __init__(self, payload=None, error=None):
        self.calls = 0
        self.payload, self.error = payload, error

    def __call__(self, req, timeout=None):
        import io
        self.calls += 1
        if self.error:
            raise self.error
        class R(io.BytesIO):
            def __enter__(s): return s
            def __exit__(s, *a): return False
        return R(json.dumps(self.payload).encode())


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.custom = Path(self._tmp.name) / "lyrics"
        self.cache = Path(self._tmp.name) / "cache"

    def test_prefers_custom_without_network(self):
        save_custom("J", "A", "[00:01.00]mine", self.custom)
        op = Opener(error=RuntimeError("no network expected"))
        res = resolve_lyrics("J", "A", "Al", 100.0, self.cache, self.custom, opener=op)
        self.assertEqual(res, Lyrics([(1.0, "mine")], True))
        self.assertEqual(op.calls, 0)

    def test_falls_back_to_lrclib(self):
        op = Opener({"plainLyrics": "online"})
        res = resolve_lyrics("J", "A", "Al", 100.0, self.cache, self.custom, opener=op)
        self.assertEqual(res.lines, [(0.0, "online")])
        self.assertEqual(op.calls, 1)

    def test_non_utf8_custom_falls_back_to_lrclib(self):
        self.custom.mkdir(parents=True)
        (self.custom / "A - J.txt").write_bytes(b"\xff\xfe\x00")
        op = Opener({"plainLyrics": "online"})
        res = resolve_lyrics("J", "A", "Al", 100.0, self.cache, self.custom, opener=op)
        self.assertEqual(res.lines, [(0.0, "online")])


if __name__ == "__main__":
    unittest.main()
