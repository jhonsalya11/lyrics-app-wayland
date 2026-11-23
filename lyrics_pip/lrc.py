import bisect
import re

_TS = re.compile(r"\[(\d+):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def parse_lrc(text: str) -> list[tuple[float, str]]:
    """Parse LRC text into sorted (seconds, text) pairs."""
    result: list[tuple[float, str]] = []
    for raw in (text or "").splitlines():
        raw = raw.lstrip()  # pasted lyrics are often indented
        stamps = []
        pos = 0
        while True:
            m = _TS.match(raw, pos)
            if not m:
                break
            minutes, seconds, frac = m.group(1), m.group(2), m.group(3)
            t = int(minutes) * 60 + int(seconds)
            if frac:
                t += int(frac) / (10 ** len(frac))
            stamps.append(t)
            pos = m.end()
        if not stamps:
            continue
        line = raw[pos:].strip()
        for t in stamps:
            result.append((float(t), line))
    result.sort(key=lambda x: x[0])
    return result


def active_index(lines: list[tuple[float, str]], position: float) -> int:
    """Index of the line active at `position`, or -1 if none yet."""
    if not lines:
        return -1
    times = [t for t, _ in lines]
    return bisect.bisect_right(times, position) - 1
