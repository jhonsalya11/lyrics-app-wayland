import unittest

from lyrics_pip.clock import PositionEstimator


class PositionEstimatorTest(unittest.TestCase):
    def test_interpolates_within_a_second_and_caps(self):
        e = PositionEstimator()
        self.assertAlmostEqual(e.update(10.0, 100.0, True), 10.5)
        self.assertAlmostEqual(e.update(10.0, 100.3, True), 10.8)
        self.assertAlmostEqual(e.update(10.0, 100.9, True), 11.0)  # capped

    def test_natural_advance_reanchors_without_going_backwards(self):
        e = PositionEstimator()
        e.update(10.0, 100.0, True)
        e.update(10.0, 100.9, True)
        self.assertAlmostEqual(e.update(11.0, 101.0, True), 11.0)
        self.assertAlmostEqual(e.update(11.0, 101.4, True), 11.4)

    def test_seek_reanchors(self):
        e = PositionEstimator()
        e.update(10.0, 100.0, True)
        self.assertAlmostEqual(e.update(50.0, 100.2, True), 50.5)
        self.assertAlmostEqual(e.update(5.0, 100.4, True), 5.5)  # backwards seek

    def test_pause_freezes_and_resume_continues(self):
        e = PositionEstimator()
        e.update(10.0, 100.0, True)
        self.assertAlmostEqual(e.update(10.0, 100.3, False), 10.8)
        self.assertAlmostEqual(e.update(10.0, 105.0, False), 10.8)
        self.assertAlmostEqual(e.update(10.0, 106.0, True), 10.8)
        self.assertAlmostEqual(e.update(10.0, 106.1, True), 10.9)

    def test_seek_while_paused(self):
        e = PositionEstimator()
        e.update(10.0, 100.0, True)
        self.assertAlmostEqual(e.update(30.0, 101.0, False), 30.5)
        self.assertAlmostEqual(e.update(30.0, 102.0, False), 30.5)


if __name__ == "__main__":
    unittest.main()
