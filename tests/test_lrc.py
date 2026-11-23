import unittest

from lyrics_pip.lrc import active_index, parse_lrc


class ParseLrcTest(unittest.TestCase):
    def test_parse_basic(self):
        self.assertEqual(
            parse_lrc("[00:12.50]Halo\n[01:02.00]Dunia"),
            [(12.5, "Halo"), (62.0, "Dunia")],
        )

    def test_parse_multiple_timestamps(self):
        self.assertEqual(
            parse_lrc("[00:01.00][00:05.00]Ulang"),
            [(1.0, "Ulang"), (5.0, "Ulang")],
        )

    def test_parse_ignores_metadata_and_garbage(self):
        text = "[ar:Artis]\n[ti:Judul]\nbaris tanpa timestamp\n\n[xx:yy]rusak"
        self.assertEqual(parse_lrc(text), [])
        self.assertEqual(parse_lrc(""), [])

    def test_parse_keeps_empty_text_lines_as_gaps(self):
        self.assertEqual(parse_lrc("[00:10.00]"), [(10.0, "")])

    def test_parse_accepts_leading_whitespace(self):
        self.assertEqual(
            parse_lrc("  [00:01.00]a\n\t[00:02.00]b"), [(1.0, "a"), (2.0, "b")]
        )

    def test_parse_sorts_output(self):
        self.assertEqual(
            parse_lrc("[00:05.00]b\n[00:01.00]a"), [(1.0, "a"), (5.0, "b")]
        )


class ActiveIndexTest(unittest.TestCase):
    def test_active_index(self):
        lines = [(1.0, "a"), (5.0, "b")]
        self.assertEqual(active_index(lines, 0.5), -1)
        self.assertEqual(active_index(lines, 1.0), 0)
        self.assertEqual(active_index(lines, 4.99), 0)
        self.assertEqual(active_index(lines, 5.0), 1)
        self.assertEqual(active_index(lines, 99), 1)
        self.assertEqual(active_index([], 3.0), -1)


if __name__ == "__main__":
    unittest.main()
