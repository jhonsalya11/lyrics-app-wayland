import fcntl
import os
from pathlib import Path


class _NoLock:
    """Stand-in when the lock file cannot be created: never block startup."""

    def close(self) -> None:
        pass


def acquire_single_instance(path: Path):
    """Take an exclusive lock on `path`.

    Returns a handle to keep alive for the process lifetime (the lock is released
    when it is closed or the process exits), or None if another instance holds it.
    """
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        return _NoLock()
    handle = os.fdopen(fd, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle
