import json
import tempfile
import unittest
from pathlib import Path

from lyrics_pip.ui import load_config, save_config


class SyncOffsetConfigTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "config.json"

    def offset(self, value):
        self.path.write_text(json.dumps({"sync_offset": value}))
        return load_config(self.path)["sync_offset"]

    def test_default_is_0_3(self):
        self.assertEqual(load_config(self.path)["sync_offset"], 0.3)

    def test_valid_values(self):
        self.assertEqual(self.offset(0.5), 0.5)
        self.assertEqual(self.offset(0), 0.0)  # zero is legitimate, not replaced by the default

    def test_invalid_falls_back_to_default(self):
        self.assertEqual(self.offset("abc"), 0.3)
        self.assertEqual(self.offset(None), 0.3)

    def test_clamped_to_range(self):
        self.assertEqual(self.offset(99), 2.0)
        self.assertEqual(self.offset(-1), 0.0)

    def test_save_config_keeps_sync_offset(self):
        self.path.write_text(json.dumps({"sync_offset": 0.7}))
        save_config(load_config(self.path), self.path)
        self.assertEqual(load_config(self.path)["sync_offset"], 0.7)


if __name__ == "__main__":
    unittest.main()
