class PositionEstimator:
    """Smooths MPRIS Position, which Firefox reports only in whole seconds.

    The real position lies in [reported, reported + 1). We anchor on the moment
    the reported value changes and interpolate with the monotonic clock.
    """

    def __init__(self):
        self._rep = None
        self._apos = 0.0
        self._atime = 0.0
        self._est = 0.0
        self._playing = True

    def _anchor(self, pos: float, now: float) -> None:
        self._apos = pos
        self._atime = now
        self._est = pos

    def _interpolate(self, reported: float, now: float) -> float:
        est = min(self._apos + (now - self._atime), reported + 1.0)
        return max(est, reported)

    def update(self, reported: float, now: float, playing: bool) -> float:
        if self._rep is None or reported < self._rep or reported - self._rep > 1.5:
            self._anchor(reported + 0.5, now)  # first reading or seek
        elif reported != self._rep:
            self._anchor(reported, now)  # natural second boundary
        elif playing and not self._playing:
            self._anchor(self._est, now)  # resumed from pause
        elif not playing and self._playing:
            self._est = self._interpolate(reported, now)  # just paused: freeze
        elif playing:
            self._est = self._interpolate(reported, now)

        self._rep = reported
        self._playing = playing
        return self._est
