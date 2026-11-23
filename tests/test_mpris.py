import unittest

from lyrics_pip.mpris import Track, parse_metadata


class ParseMetadataTest(unittest.TestCase):
    def test_full_metadata(self):
        meta = {
            "xesam:title": "Judul",
            "xesam:artist": ["Artis"],
            "xesam:album": "Album",
            "mpris:length": 215000000,
        }
        self.assertEqual(parse_metadata(meta), Track("Judul", "Artis", "Album", 215.0))

    def test_empty_artist_list(self):
        meta = {"xesam:title": "Judul", "xesam:artist": []}
        self.assertEqual(parse_metadata(meta).artist, "")

    def test_no_title_returns_none(self):
        self.assertIsNone(parse_metadata({"xesam:artist": ["A"]}))
        self.assertIsNone(parse_metadata({"xesam:title": ""}))
        self.assertIsNone(parse_metadata({}))

    def test_missing_length(self):
        self.assertEqual(parse_metadata({"xesam:title": "J"}).length, 0.0)

    def test_multiple_artists_joined(self):
        meta = {"xesam:title": "J", "xesam:artist": ["A", "B"]}
        self.assertEqual(parse_metadata(meta).artist, "A, B")


if __name__ == "__main__":
    unittest.main()
