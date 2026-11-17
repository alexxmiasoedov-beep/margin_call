"""s74 — откат хода выходных на фьючерсах Binance на акции и сырьё (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Ход выходных m = цена E (воскресенье, 15 мин до открытия CME) / цена C (закрытие пятницы) − 1; при |m| ≥ 1% — сделка против
хода: вход по закрытию свечи в E, выход в X (акции — открытие NYSE + 15 мин в понедельник; сырьё — открытие CME + 2 ч),
стоп 20%, без тейка, комиссия и фандинг (s15/common.trade). Плацебо — та же бумага, та же неделя: окно той же длины от
закрытия во вторник до часа E в четверг, выход в тот же час X в пятницу. Половины — по медианной дате событий.
Запуск из папки с данными."""
import datetime
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import DAY, ct  # noqa: E402

STOCKS = ["AAPL", "AMD", "AMZN", "COIN", "CRCL", "GOOGL", "HOOD", "INTC", "META", "MSFT", "MSTR", "MU", "NVDA", "PLTR", "QQQ",
          "SNDK", "SOXL", "SOXS", "SPY", "TSLA"]
COMM = ["XAU", "XAG", "XPT", "XPD", "COPPER", "CL", "BZ", "NATGAS"]
HOLI = {"2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
        "2025-12-25", "2026-01-02"}
NY = ZoneInfo("America/New_York")
UTC = datetime.timezone.utc


def ts(d, hh, mm=0):
    """Метка UTC для местного времени Нью-Йорка (дата d, часы hh:mm)."""
    return int(datetime.datetime(d.year, d.month, d.day, hh, mm, tzinfo=NY).timestamp())


def close_at(s, T):
    """Индекс 15-мин свечи, закрывающейся в T (открытие T − 15 мин), если она есть и с оборотом."""
    t = K[s]["t"]; i = int(np.searchsorted(t, T - 900))
    return i if i < len(t) and t[i] == T - 900 and K[s]["qv"][i] > 0 else None


def windows(fri, cls):
    """Точки C, E, X (UTC) для выходных после пятницы fri и для плацебо (вторник → четверг → пятница)."""
    sun, mon = fri + datetime.timedelta(2), fri + datetime.timedelta(3)
    tue, thu = fri - datetime.timedelta(3), fri - datetime.timedelta(1)
    if cls == "stock":
        C, C2 = ts(fri, 16), ts(tue, 16)                        # закрытие NYSE 16:00 ET
        X, X2 = ts(mon, 9, 45), ts(fri, 9, 45)                  # открытие NYSE 9:30 ET + 15 мин
    else:
        C, C2 = ts(fri, 17), ts(tue, 17)                        # закрытие CME 16:00 CT = 17:00 ET
        X, X2 = ts(sun, 20), ts(thu, 20)                        # открытие CME 18:00 ET + 2 ч
    E, E2 = ts(sun, 17, 45), ts(thu, 17, 45)                    # 15 мин до открытия CME (18:00 ET)
    return (C, E, X), (C2, E2, X2)


def fade(s, C, E, X, thr=0.01):
    i0, i = close_at(s, C), close_at(s, E)
    if i0 is None or i is None:
        return None
    c = K[s]["c"]; m = float(c[i] / c[i0] - 1)
    if abs(m) < thr:
        return dict(m=m, net=np.nan)
    side = -1 if m > 0 else 1
    x = trade(s, i, tp=None, sl=0.20, hold_h=(X - E) / 3600, side=side)
    return dict(m=m, net=x["net"] if x else np.nan)


def main():
    rows = []
    fri = datetime.date(2025, 12, 5)
    while fri <= datetime.date(2026, 10, 16):
        mon = fri + datetime.timedelta(3)
        if fri.isoformat() not in HOLI and mon.isoformat() not in HOLI:
            for cls, syms in (("stock", STOCKS), ("comm", COMM)):
                (C, E, X), (C2, E2, X2) = windows(fri, cls)
                for s in syms:
                    if s not in K:
                        continue
                    lo, hi = live(s)
                    if C < lo + 7 * DAY or X > hi:
                        continue
                    ev = fade(s, C, E, X)
                    if ev is None or np.isnan(ev["net"]):
                        continue
                    pl = fade(s, C2, E2, X2) if C2 >= lo + 7 * DAY else None
                    rows.append(dict(s=s, cls=cls, t=E, m=ev["m"], net=ev["net"],
                                     pl=pl["net"] if pl else np.nan, pm=pl["m"] if pl else np.nan))
        fri += datetime.timedelta(7)
    X = pd.DataFrame(rows)
    X.to_pickle("s74/trades.pkl")
    mid = X.t.median()
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Сделок {len(X)} ({len(X) / months:.1f} в месяц), выходных {X.t.nunique()}; половины до/после "
          f"{datetime.datetime.fromtimestamp(mid, UTC):%d.%m.%Y}; |m| медиана {X.m.abs().median():.2%}")
    for lab, x in (("все (основная)", X), ("акции и фонды", X[X.cls == "stock"]), ("сырьё", X[X.cls == "comm"]),
                   ("|m| ≥ 2%", X[X.m.abs() >= 0.02]), ("рост за выходные → шорт", X[X.m > 0]), ("падение → лонг", X[X.m < 0])):
        if len(x) < 8:
            continue
        m, t, n = ct(x.net, x.t)
        h1, h2 = x[x.t < mid], x[x.t >= mid]
        (m1, t1, _), (m2, t2, _) = ct(h1.net, h1.t), ct(h2.net, h2.t)
        y = x[x.pl.notna()]
        dp, tp, npl = ct(y.net - y.pl, y.t)
        print(f"  {lab:24s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
              f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо (n={npl}) {y.pl.mean():+6.2%},"
              f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
