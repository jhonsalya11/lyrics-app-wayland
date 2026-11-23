import unittest

from lyrics_pip.syncer import SyncSession, format_timestamp


class FormatTimestampTest(unittest.TestCase):
    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(62.5), "[01:02.50]")
        self.assertEqual(format_timestamp(0), "[00:00.00]")
        self.assertEqual(format_timestamp(3605), "[60:05.00]")
        self.assertEqual(format_timestamp(59.999), "[01:00.00]")


class SyncSessionTest(unittest.TestCase):
    def test_blank_lines_are_skipped_and_text_stripped(self):
        self.assertEqual(SyncSession(["a", "", "  b  ", "   "]).texts, ["a", "b"])

    def test_mark_subtracts_offset_and_clamps_at_zero(self):
        s = SyncSession(["a", "b"])
        self.assertAlmostEqual(s.mark(0, 10.0, 0.3), 9.7)
        self.assertEqual(s.mark(1, 0.1, 0.3), 0.0)
        with self.assertRaises(IndexError):
            s.mark(5, 1.0, 0.3)

    def test_mark_next_goes_in_order_then_stops(self):
        s = SyncSession(["a", "b"])
        self.assertEqual(s.mark_next(1.0, 0.0), 0)
        self.assertEqual(s.mark_next(2.0, 0.0), 1)
        self.assertIsNone(s.mark_next(3.0, 0.0))
        self.assertEqual(s.stamps, [1.0, 2.0])

    def test_mark_next_with_only_two_of_three_done(self):
        s = SyncSession(["a", "b", "c"])
        s.mark_next(1.0, 0.0)
        s.mark_next(2.0, 0.0)
        self.assertEqual(s.stamps, [1.0, 2.0, None])

    def test_next_index_is_first_unstamped(self):
        s = SyncSession(["a", "b", "c"])
        s.mark(2, 5.0, 0.0)
        self.assertEqual(s.next_index(), 0)
        s.mark(0, 1.0, 0.0)
        s.mark(1, 2.0, 0.0)
        self.assertIsNone(s.next_index())

    def test_done_total_complete(self):
        empty = SyncSession(["", "  "])
        self.assertEqual((empty.done(), empty.total(), empty.is_complete()), (0, 0, False))
        s = SyncSession(["a", "b"])
        s.mark(0, 1.0, 0.0)
        self.assertEqual((s.done(), s.total(), s.is_complete()), (1, 2, False))
        s.mark(1, 2.0, 0.0)
        self.assertEqual((s.done(), s.total(), s.is_complete()), (2, 2, True))

    def test_first_out_of_order(self):
        def check(stamps):
            s = SyncSession(["x"] * len(stamps))
            s.stamps = list(stamps)
            return s.first_out_of_order()

        self.assertEqual(check([1.0, 2.0, 1.5]), 2)
        self.assertIsNone(check([1.0, 1.0, 2.0]))
        self.assertEqual(check([5.0, None, 3.0]), 2)
        self.assertIsNone(check([1.0, 2.0, 3.0]))

    def test_to_lrc_requires_complete_and_formats_lines(self):
        s = SyncSession(["a", "b"])
        s.mark(0, 1.0, 0.0)
        with self.assertRaises(ValueError):
            s.to_lrc()
        s.mark(1, 2.5, 0.0)
        self.assertEqual(s.to_lrc(), "[00:01.00]a\n[00:02.50]b")


if __name__ == "__main__":
    unittest.main()
