"""s188 — проба по часовой ставке займа OKX (okx_rates.py): живость ряда и события загрузки пула (без доходов).
Сутки UTC → ставка на конец суток; загрузка x = ставка / 10-й перцентиль своих прошлых 30 сут; события «x ≥ 3 впервые
за 7 сут» в месяц: 01.2022–01.2023 (когда ставка Binance ещё ручная) и 02.2023–05.2023; сравнение с Binance на тех же
монетах (bnrates). Пересечения со входами журналов — ±7 сут. Запуск: python3 -I okx_probe.py."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

DAY = 86400
OK = "/home/user/mc_data/s188/okx"
BN = "/home/user/mc_data/s188/bnrates"
SEG = [("01.2022–01.2023", C.ts("2022-01-01"), C.ts("2023-02-01")),
       ("02.2023–05.2023", C.ts("2023-02-01"), C.ts("2023-06-01"))]


def daily(fn, col=1):
    x = pd.read_csv(fn, header=None)
    x["d"] = (x[0] // DAY) * DAY
    s = x.groupby("d")[col].last()
    return s.reindex(np.arange(s.index.min(), s.index.max() + DAY, DAY)).ffill()


def events(s, t0, t1):
    fl = s.rolling(30, min_periods=20).quantile(0.10).shift(1)
    x = s / fl
    hit = x[(x >= 3) & (x.index >= t0) & (x.index < t1)].index
    out, last = [], -10 ** 12
    for t in hit:
        if t - last >= 7 * DAY:
            out.append(t)
            last = t
    return out


J = pd.concat([C.journals(p) for p in C.PERS])
jt = {s: np.sort(x.t.values) for s, x in J.groupby("s")}
for name, t0, t1 in SEG:
    mon = (t1 - t0) / (30.4 * DAY)
    res = {"OKX": [], "Binance": []}
    live = {"OKX": [], "Binance": []}
    for f in sorted(os.listdir(OK)):
        c = f[:-4]
        for src, fn in (("OKX", f"{OK}/{f}"), ("Binance", f"{BN}/{c}.csv")):
            if not os.path.exists(fn) or os.path.getsize(fn) == 0:
                continue
            s = daily(fn)
            ins = s[(s.index >= t0) & (s.index < t1)]
            if len(ins) < 60:
                continue
            live[src].append((ins.diff() != 0).mean())
            res[src] += [(c, t) for t in events(s, t0, t1)]
    print(f"\n== {name}")
    for src in ("OKX", "Binance"):
        ev = res[src]
        if not live[src]:
            print(f"  {src}: нет рядов")
            continue
        ov = np.mean([c in jt and np.any(np.abs(jt[c] - t) <= 7 * DAY) for c, t in ev]) if ev else np.nan
        print(f"  {src}: монет {len(live[src])}, доля суток со сменой ставки — медиана {np.median(live[src]):.0%}; "
              f"x ≥ 3 впервые за 7 сут: {len(ev)} ({len(ev) / mon:.1f} в месяц), вход журнала ±7 сут {ov:.0%}")
    both = set((c, t // (7 * DAY)) for c, t in res["OKX"]) & set((c, t // (7 * DAY)) for c, t in res["Binance"])
    print(f"  совпадение недель «OKX и Binance одновременно»: {len(both)}")
