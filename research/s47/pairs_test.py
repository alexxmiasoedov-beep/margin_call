"""s47 — снятие спотовых пар Binance (гипотеза — ВЫВОДЫ.md, записана до проверки). События — монеты с фьючерсом Binance
старше суток, чьи пары (кроме USDT) названы в «Notice of Removal of Spot Trading Pairs» (s44/pair_removals.json); без монет
с объявлением о делистинге в ±7 сут (s44/delist_list.json); не чаще раза в 7 сут на монету. Шорт с закрытия первой 15-мин
свечи после публикации: основной — 7 сут без тейка, стоп +25% (как 📢); для сравнения S_7_20 и S_10_15. Плацебо — та же
монета за 45/90/135 сут. Запуск из папки с данными."""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EXITS = {"AN_7d": dict(tp=None, sl=0.25, hold_h=168), "S_7_20": dict(tp=0.07, sl=0.20, hold_h=48),
         "S_10_15": dict(tp=0.10, sl=0.15, hold_h=24)}
STOP = {"BINANCE", "WILL", "DELIST", "USD", "USDT", "USDC", "UTC", "ON", "AND", "THE", "OF", "M", "TO"}


def delist_times():
    out = {}
    for a in json.load(open("s44/delist_list.json")):
        t = a["title"]
        if "Will Delist" not in t or "Margin" in t or "Removal" in t:
            continue
        for w in re.findall(r"\b[A-Z0-9]{2,15}\b", t):
            if w in STOP:
                continue
            b = re.sub(r"(USDT|USDC)$", "", w)
            s, _ = fut_of(b)
            if s:
                out.setdefault(s, []).append(a["ts"])
    return out


def main():
    R = json.load(open("s44/pair_removals.json"))
    DL = delist_times()
    ev = []
    for v in R.values():
        for b in sorted({b for b, q in v["pairs"] if q != "USDT"}):
            s, _ = fut_of(b)
            if s and s in K:
                ev.append((s, float(v["ts"])))
    ev.sort(key=lambda x: x[1])
    rows, last = [], {}
    n_dl = 0
    for s, ts in ev:
        if ts - last.get(s, -1e18) < 7 * DAY:
            continue
        if any(abs(ts - d) <= 7 * DAY for d in DL.get(s, [])):
            n_dl += 1
            continue
        lo, hi = live(s)
        if ts < lo + DAY or ts > hi:
            continue
        i = idx_at(s, ts)
        if i is None:
            continue
        last[s] = ts
        d = dict(s=s, t=ts)
        for ex, kw in EXITS.items():
            x = trade(s, i + 1, side=-1, **kw)
            d[ex] = x["net"] if x else np.nan
            p = []
            for dd in (45, 90, 135):
                j = idx_at(s, ts - dd * DAY)
                if j is not None:
                    y = trade(s, j + 1, side=-1, **kw)
                    if y:
                        p.append(y["net"])
            d["pl_" + ex] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s47/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий: {len(X)} ({len(X) / months:.1f} в месяц), монет {X.s.nunique()}; исключено рядом с делистингом: {n_dl}")
    for ex in EXITS:
        x = X[X[ex].notna()]
        m, t, n = ct(x[ex], x.t); dp, tp, _ = ct(x[ex] - x["pl_" + ex], x.t)
        h1, h2 = x[x.t < CUT][ex].mean(), x[x.t >= CUT][ex].mean()
        print(f"  {ex:8s} n={n} {m:+.2%} (t {t:+.1f}) в плюсе {(x[ex] > 0).mean():.0%} | половины {h1:+.2%} / {h2:+.2%} |"
              f" плацебо {x['pl_' + ex].mean():+.2%}, разница {dp:+.2%} (t {tp:+.1f})")


if __name__ == "__main__":
    main()
