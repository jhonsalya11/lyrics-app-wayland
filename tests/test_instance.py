import tempfile
import unittest
from pathlib import Path

from lyrics_pip.instance import acquire_single_instance


class SingleInstanceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "sub" / "lock"

    def test_second_acquire_fails_while_first_is_held(self):
        first = acquire_single_instance(self.path)
        self.assertIsNotNone(first)
        self.assertIsNone(acquire_single_instance(self.path))
        first.close()

    def test_lock_is_released_on_close(self):
        first = acquire_single_instance(self.path)
        first.close()
        again = acquire_single_instance(self.path)
        self.assertIsNotNone(again)
        again.close()

    def test_unwritable_location_does_not_block_startup(self):
        # If the lock cannot be created at all, don't refuse to run.
        self.assertIsNotNone(acquire_single_instance(Path("/proc/nope/lock")))


if __name__ == "__main__":
    unittest.main()
