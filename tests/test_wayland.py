import unittest

from lyrics_pip.ui import (MIN_H, MIN_W, clamp_margin, default_margin, drag_geometry,
                           pick_monitor)


class ClampMarginTest(unittest.TestCase):
    def test_inside_is_kept(self):
        self.assertEqual(clamp_margin(100, 50, 380, 300, 1920, 1080), (100, 50))

    def test_pushed_back_onto_monitor(self):
        self.assertEqual(clamp_margin(1800, 1000, 380, 300, 1920, 1080), (1540, 780))
        self.assertEqual(clamp_margin(-20, -5, 380, 300, 1920, 1080), (0, 0))

    def test_window_larger_than_monitor_sticks_to_corner(self):
        self.assertEqual(clamp_margin(50, 50, 2000, 1200, 1920, 1080), (0, 0))


class DefaultMarginTest(unittest.TestCase):
    def test_top_right(self):
        self.assertEqual(default_margin(380, 300, 1920, 1080), (1500, 60))

    def test_portrait_monitor(self):
        self.assertEqual(default_margin(380, 300, 1080, 1920), (660, 60))


class PickMonitorTest(unittest.TestCase):
    MODELS = ["LG IPS FULLHD", "H27G30Q"]

    def test_found(self):
        self.assertEqual(pick_monitor("H27G30Q", self.MODELS), 1)

    def test_unplugged_or_unset(self):
        self.assertIsNone(pick_monitor("OTHER", self.MODELS))
        self.assertIsNone(pick_monitor(None, self.MODELS))


class DragGeometryTest(unittest.TestCase):
    START = (100, 100, 380, 300)

    def test_move(self):
        self.assertEqual(drag_geometry(None, self.START, 30, -20), (130, 80, 380, 300))

    def test_resize_right_bottom(self):
        self.assertEqual(drag_geometry({"right", "bottom"}, self.START, 20, 10),
                         (100, 100, 400, 310))

    def test_resize_left_top_moves_origin(self):
        self.assertEqual(drag_geometry({"left", "top"}, self.START, 20, 10),
                         (120, 110, 360, 290))

    def test_minimum_size_keeps_opposite_side(self):
        x, y, w, h = drag_geometry({"left"}, self.START, 1000, 0)
        self.assertEqual((w, x + w), (MIN_W, 100 + 380))
        _, _, _, h = drag_geometry({"bottom"}, self.START, 0, -1000)
        self.assertEqual(h, MIN_H)


if __name__ == "__main__":
    unittest.main()
