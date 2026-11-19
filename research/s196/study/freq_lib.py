"""s196 — общие функции частот: обращение CMC на дату, пороги, сводка событий по периодам (без доходов)."""
import bisect
import json
import os
import time
from common196 import OUT, PERIODS, ts, DAY

THR = (0.0005, 0.001, 0.005, 0.01)


class Circ:
    """обращение монеты на дату (последнее известное ≤ даты, CMC; дневная запись известна со следующего дня)."""
    def __init__(self, sym):
        p = f"{OUT}/circ/{sym}.json"
        rows = json.load(open(p)) if os.path.exists(p) else []
        rows = [(ts(d) + DAY, c) for d, c, _ in rows if c]
        rows.sort()
        self.t = [r[0] for r in rows]
        self.c = [r[1] for r in rows]

    def at(self, t):
        if not self.t:
            return None
        i = bisect.bisect_right(self.t, t) - 1
        if i < 0:
            return self.c[0] if self.t[0] - t < 45 * DAY else None
        return self.c[i]


def pname(t):
    for n, a, b in PERIODS:
        if ts(a) <= t < ts(b):
            return n
    return None


def day(t):
    return int(t // DAY * DAY)


def fmt_t(t):
    return time.strftime("%Y-%m-%d", time.gmtime(t))


def summarize(events, months_by_period, label, thr=THR, out=print):
    """events: [(t, доля обращения)]; months_by_period: {период: месяцев охвата}. Печать: событий в месяц ≥ порогов."""
    head = f"{label:38s}" + "".join(f" | {p:^22s}" for p, _, _ in PERIODS)
    out(head)
    for th in thr:
        cells = []
        for p, _, _ in PERIODS:
            m = months_by_period.get(p)
            if not m:
                cells.append(f"{'—':^22s}")
                continue
            n = sum(1 for t, f in events if pname(t) == p and f >= th)
            cells.append(f"{n:5d} за {m:5.1f} мес → {n / m:5.1f}")
        out(f"  ≥ {100 * th:4.2f}% обращения{'':17s}" + "".join(f" | {c:22s}" for c in cells))
