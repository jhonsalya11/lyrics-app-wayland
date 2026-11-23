import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from lyrics_pip.lyrics import NETWORK_ERROR, Lyrics, clean_title, fetch_lyrics, forget_cached


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.urls = []

    def __call__(self, req, timeout=None):
        self.urls.append(getattr(req, "full_url", req))
        if self.error:
            raise self.error
        return FakeResponse(json.dumps(self.payload).encode())


def http404():
    return urllib.error.HTTPError("u", 404, "Not Found", {}, None)


class CleanTitleTest(unittest.TestCase):
    def test_clean_title(self):
        self.assertEqual(clean_title("Judul (Official Video)"), "Judul")
        self.assertEqual(clean_title("Judul [Lyrics]"), "Judul")
        self.assertEqual(clean_title("Judul"), "Judul")

    def test_clean_title_multiple_and_variant_suffixes(self):
        self.assertEqual(clean_title("Song (Official Video) [4K]"), "Song")
        self.assertEqual(clean_title("Song (Official Audio)"), "Song")
        self.assertEqual(clean_title("Song [Official Lyric Video]"), "Song")
        self.assertEqual(clean_title("Song (Lyrics) [HD]"), "Song")

    def test_clean_title_keeps_real_title_parts(self):
        self.assertEqual(clean_title("Song (Videotape Version)"), "Song (Videotape Version)")
        self.assertEqual(clean_title("Song (Remastered 2011)"), "Song (Remastered 2011)")

    def test_clean_title_drops_leading_artist_only_when_it_matches(self):
        self.assertEqual(clean_title("Alesana - Song", "Alesana"), "Song")
        self.assertEqual(clean_title("alesana - Song (Official Video)", "Alesana"), "Song")
        self.assertEqual(clean_title("Other - Song", "Alesana"), "Other - Song")
        self.assertEqual(clean_title("Alesana - B - C", "Alesana"), "B - C")
        self.assertEqual(clean_title("Alesana - Song"), "Alesana - Song")


class FetchLyricsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_fetch_synced(self):
        op = FakeOpener({"syncedLyrics": "[00:01.00]a", "plainLyrics": "a"})
        res = fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=op)
        self.assertEqual(res, Lyrics([(1.0, "a")], True))
        url = op.urls[0]
        for key in ("track_name", "artist_name", "album_name", "duration"):
            self.assertIn(key, url)

    def test_fetch_plain_fallback(self):
        op = FakeOpener({"syncedLyrics": None, "plainLyrics": "a\nb"})
        res = fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=op)
        self.assertFalse(res.synced)
        self.assertEqual([t for _, t in res.lines], ["a", "b"])

    def test_cache_hit_skips_network(self):
        op = FakeOpener({"syncedLyrics": "[00:01.00]a"})
        first = fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=op)
        bad = FakeOpener(error=urllib.error.URLError("down"))
        second = fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=bad)
        self.assertEqual(first, second)
        self.assertEqual(bad.urls, [])

    def test_not_found_returns_none_and_is_cached(self):
        op = FakeOpener(error=http404())
        self.assertIsNone(fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=op))
        again = FakeOpener(error=http404())
        self.assertIsNone(fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=again))
        self.assertEqual(again.urls, [])

    def test_network_error_returns_none_not_raise_and_not_cached(self):
        down = FakeOpener(error=urllib.error.URLError("down"))
        self.assertIs(fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=down), NETWORK_ERROR)
        up = FakeOpener({"syncedLyrics": "[00:01.00]a"})
        res = fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=up)
        self.assertIsNotNone(res)
        self.assertEqual(len(up.urls), 1)

    def test_empty_artist_still_works(self):
        op = FakeOpener({"plainLyrics": "a"})
        res = fetch_lyrics("T", "", "", 0.0, self.cache, opener=op)
        self.assertIsNotNone(res)

    def test_empty_lyrics_payload_is_not_found(self):
        op = FakeOpener({"syncedLyrics": "", "plainLyrics": ""})
        self.assertIsNone(fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=op))


class ScriptedOpener:
    """Returns/raises the next scripted item per call."""

    def __init__(self, *items):
        self.items = list(items)
        self.urls = []

    def __call__(self, req, timeout=None):
        self.urls.append(req.full_url)
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(json.dumps(item).encode())


class FallbackTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_album_mismatch_retries_without_album(self):
        op = ScriptedOpener(http404(), {"syncedLyrics": "[00:01.00]a"})
        res = fetch_lyrics("T", "A", "Wrong Album", 200.0, self.cache, opener=op)
        self.assertEqual(res, Lyrics([(1.0, "a")], True))
        self.assertIn("album_name", op.urls[0])
        self.assertNotIn("album_name", op.urls[1])

    def test_search_fallback_picks_closest_duration_preferring_synced(self):
        results = [
            {"duration": 100, "syncedLyrics": "[00:01.00]far"},
            {"duration": 201, "syncedLyrics": "[00:02.00]near"},
            {"duration": 200, "syncedLyrics": None, "plainLyrics": "plain"},
        ]
        op = ScriptedOpener(http404(), http404(), results)
        res = fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=op)
        self.assertEqual(res, Lyrics([(2.0, "near")], True))
        self.assertIn("/api/search", op.urls[2])

    def test_duration_zero_is_omitted(self):
        op = ScriptedOpener({"plainLyrics": "a"})
        fetch_lyrics("T", "A", "", 0.0, self.cache, opener=op)
        self.assertNotIn("duration", op.urls[0])

    def test_all_attempts_404_is_cached_not_found(self):
        op = ScriptedOpener(http404(), http404(), [])
        self.assertIsNone(fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=op))
        again = ScriptedOpener()
        self.assertIsNone(fetch_lyrics("T", "A", "Al", 200.0, self.cache, opener=again))
        self.assertEqual(again.urls, [])


class ForgetCachedTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_forget_cached_forces_refetch(self):
        op = FakeOpener({"plainLyrics": "a"})
        fetch_lyrics("T", "A", "", 100.0, self.cache, opener=op)
        forget_cached("T", "A", 100.0, self.cache)
        fetch_lyrics("T", "A", "", 100.0, self.cache, opener=op)
        self.assertEqual(len(op.urls), 2)

    def test_forget_cached_clears_not_found_marker(self):
        fetch_lyrics("T", "A", "", 100.0, self.cache, opener=FakeOpener(error=http404()))
        forget_cached("T", "A", 100.0, self.cache)
        op = FakeOpener({"plainLyrics": "found now"})
        res = fetch_lyrics("T", "A", "", 100.0, self.cache, opener=op)
        self.assertIsNotNone(res)

    def test_forget_cached_missing_file_is_noop(self):
        forget_cached("Nope", "A", 1.0, self.cache)


if __name__ == "__main__":
    unittest.main()
