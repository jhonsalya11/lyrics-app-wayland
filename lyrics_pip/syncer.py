def format_timestamp(seconds: float) -> str:
    """LRC timestamp '[mm:ss.xx]'; rounds to centiseconds first so 59.999 -> [01:00.00]."""
    total_cs = max(0, round(seconds * 100))
    minutes, rest = divmod(total_cs, 6000)
    secs, cs = divmod(rest, 100)
    return f"[{minutes:02d}:{secs:02d}.{cs:02d}]"


class SyncSession:
    """Tap-sync state: one optional timestamp per non-blank lyric line."""

    def __init__(self, lines):
        self.texts = [ln.strip() for ln in lines if ln.strip()]
        self.stamps: list = [None] * len(self.texts)

    def mark(self, index: int, position: float, offset: float) -> float:
        if not 0 <= index < len(self.texts):
            raise IndexError(index)
        self.stamps[index] = max(0.0, position - offset)
        return self.stamps[index]

    def mark_next(self, position: float, offset: float):
        index = self.next_index()
        if index is None:
            return None
        self.mark(index, position, offset)
        return index

    def next_index(self):
        for i, stamp in enumerate(self.stamps):
            if stamp is None:
                return i
        return None

    def done(self) -> int:
        return sum(1 for s in self.stamps if s is not None)

    def total(self) -> int:
        return len(self.texts)

    def is_complete(self) -> bool:
        return self.total() > 0 and self.done() == self.total()

    def first_out_of_order(self):
        """Index of the first stamped line earlier than the previous stamped line."""
        prev = None
        for i, stamp in enumerate(self.stamps):
            if stamp is None:
                continue
            if prev is not None and stamp < prev:
                return i
            prev = stamp
        return None

    def to_lrc(self) -> str:
        if not self.is_complete():
            raise ValueError("not every line is stamped")
        return "\n".join(
            f"{format_timestamp(stamp)}{text}" for stamp, text in zip(self.stamps, self.texts)
        )
