"""s216 — честный прогон правила на всём периоде: одна сделка на монету до выхода (по сетке 4 ч в порядке времени), доход после
комиссии и фандинга, t по неделям, половины, плацебо той же монеты (±45/90/135 сут), хедж индексом альтов (s103).
Запуск из /home/user/mc_data: python3 <repo>/research/s216/final.py <исход> "<правило: признак ≤ x & признак ≥ y …>"
"""
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s187", "s182"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from features import OUTS  # noqa: E402

DAY, WEEK = 86400, 7 * 86400
MID = pd.Timestamp("2025-12-20", tz="UTC").timestamp()
PFX = os.environ.get("PFX", "s216")


def mask(D, rule):
    m = np.ones(len(D), bool)
    for c in rule.split(" & "):
        f, op, q = re.match(r"^\s*(\S+) (≤|≥) (\S+)\s*$", c).groups()
        x = D[f].to_numpy(float); q = float(q)
        m &= np.isfinite(x) & ((x <= q) if op == "≤" else (x >= q))
    return m


def ct(x, t):
    """Среднее и t по кластерам-неделям."""
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // WEEK)
    ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m, m / se if se > 0 else np.nan, len(x)


def simulate(col, rule, D=None):
    import fastbt as FB  # noqa: E402
    side, sl, hold = OUTS[col]
    D = pd.read_pickle(f"{PFX}_feat.pkl") if D is None else D
    D = D[D[col].notna()].sort_values(["T", "s"])
    X = D[mask(D, rule)]
    rows = []
    for s, g in X.groupby("s"):
        t = FB.K[s]["t"].astype(np.int64)
        st = g["T"].to_numpy(np.int64) - 900
        I = np.searchsorted(t, st)
        okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, side)
        pl = FB.placebo(s, I, sl, hold, side)
        last = -1
        for k in range(len(g)):
            if not okt[k] or st[k] + 900 < last:
                continue
            rows.append((s, int(st[k] + 900), int(tend[k]), net[k], pl[k], bool(stp[k])))
            last = tend[k]
    R = pd.DataFrame(rows, columns=["s", "t", "tend", "net", "pl", "stop"])
    mv = FB.alt_mv(R.t.to_numpy(np.int64), R.tend.to_numpy(np.int64)) if len(R) else np.zeros(0)
    R["hed"] = R.net + (mv if side < 0 else -mv)
    return R


def report(col, rule):
    R = simulate(col, rule)
    months = (R.t.max() - R.t.min()) / (30.44 * DAY) if len(R) > 1 else np.nan
    m, t, n = ct(R.net, R.t)
    mh, th, _ = ct(R.hed, R.t)
    md, td, _ = ct(R.net - R.pl, R.t)
    h1, h2 = R[R.t < MID].net.mean(), R[R.t >= MID].net.mean()
    print(f"{col} | {rule}")
    print(f"  сделок {n} ({n / months:.1f} в месяц), {m:+.2%} на сделку (t по неделям {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
          f"с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {R.stop.mean():.0%}")
    crit = [("≥ 20 в месяц", n / months >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
            ("сверх плацебо > 0", md > 0), ("с хеджем > 0", mh > 0)]
    print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
    return R


if __name__ == "__main__":
    report(sys.argv[1], sys.argv[2])
