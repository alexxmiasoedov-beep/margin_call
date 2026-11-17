"""s124 — 🅱️ на одном периоде (правило — ВЫВОДЫ.md, записано до расчёта, как s22/h10_ann.py): объявления s124/ann.pkl,
семейства list / hodler / margin, без Alpha и Futures; первое за 30 сут; фьючерс ≥ суток до объявления; шорт на закрытии
ближайшего часа после публикации, 30 сут, стоп 50% (s15/common.trade). Период — архив MC_K/MC_F.
Запуск: MC_K=… MC_F=… python3 <repo>/research/s124/bl_oos.py <метка>"""
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s105"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live, trade  # noqa: E402
from oi_test import DAY, ct, idx_at  # noqa: E402
from jumps_test import SKIP  # noqa: E402

FAM = {"list": r"\bWill List\b", "hodler": r"HODLer Airdrops|Launchpool|Megadrop",
       "margin": r"Will Add .*\bMargin\b|^Binance Adds .*\bMargin\b"}
ANN = "/home/user/mc_data/s124/ann.pkl"


def main():
    lab = sys.argv[1]
    A = pickle.load(open(ANN, "rb"))
    g = K["BTC"]["t"]; g0, g1 = float(g[0]), float(g[-1])
    raw = []
    for a in A.values():
        ts = a["ts"] / 1000; t = a["title"]
        if not (g0 + DAY <= ts <= g1 - 31 * DAY) or "Alpha" in t or "Futures" in t:
            continue
        for fam, p in FAM.items():
            if re.search(p, t):
                for tok in re.findall(r"\(([^()\s,]{1,20})\)", t):
                    s = tok if tok in K else fut_of(tok)[0]
                    if s and s not in SKIP:
                        raw.append((s, ts, fam))
    R = pd.DataFrame(raw, columns=["s", "ts", "fam"]).drop_duplicates().sort_values("ts")
    rows = []
    for s, gg in R.groupby("s"):
        last = -1e18
        for ts, fam in zip(gg.ts.values, gg.fam.values):
            if ts - last < 30 * DAY:
                continue
            last = ts
            lo, hi = live(s)
            if lo > ts - DAY:
                continue
            T = (int(ts) // 3600 + 1) * 3600
            i = idx_at(s, T)
            if i is None:
                continue
            x = trade(s, i, tp=None, sl=0.5, hold_h=720, side=-1)
            if x:
                rows.append(dict(s=s, t=float(T), fam=fam, net=x["net"], why=x["why"]))
    X = pd.DataFrame(rows)
    X.to_pickle(f"s124_{lab}.pkl")
    m, t, n = ct(X.net, X.t)
    months = (g1 - g0) / (30.4 * DAY)
    print(f"{lab}: событий {n} ({n / months:.1f} в мес.), шорт 30 сут {m:+.2%} (t {t:+.1f}), в плюсе {(X.net > 0).mean():.0%}, "
          f"стопов {(X.why == 'стоп').mean():.0%}; по семействам " + ", ".join(f"{k} {v.net.mean():+.1%} ({len(v)})" for k, v in X.groupby("fam")))


if __name__ == "__main__":
    main()
