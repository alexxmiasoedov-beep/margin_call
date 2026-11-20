"""s219 — честный прогон правила на отрезке C (10.2024–10.2026): одна сделка на монету до выхода (по дням в порядке времени),
доход без хеджа и с хеджем индексом альтов, плацебо той же монеты, половины C, частота, совпадение со входами действующих
журналов (порог 4 ВЫВОДЫ.md). Запуск из /home/user/mc_data:
  python3 <repo>/research/s219/final.py <исход y_s24|…> "<правило>" """
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s187", "s96", "s219"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from features import OUTS  # noqa: E402  (s219)

DAY, WEEK = 86400, 7 * 86400
C0 = pd.Timestamp("2024-10-01", tz="UTC").timestamp()
MID = pd.Timestamp("2025-10-01", tz="UTC").timestamp()


def mask(D, rule):
    m = np.ones(len(D), bool)
    for c in rule.split(" & "):
        f, op, q = re.match(r"^\s*(\S+) (≤|≥|≠) (\S+)\s*$", c).groups()
        x = D[f].to_numpy(float); q = float(q)
        m &= np.isfinite(x) & ((x <= q) if op == "≤" else (x >= q) if op == "≥" else (x != q))
    return m


def ct(x, t):
    x = np.asarray(x, float); w = np.asarray(t, np.int64) // WEEK
    ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m, m / se if se > 0 else np.nan, len(x)


def journals():
    """Входы действующих журналов на 2024–2026: {монета: массив времён входа}."""
    from portfolio import load  # noqa: E402  (s96)
    X = load()[["s", "t"]]
    U = pd.read_pickle("s142_2024–2026.pkl")[["s", "t"]]                       # 🔑⁺
    W = pd.read_pickle("s213_main_2024–2026.pkl")[["perp", "t"]].rename(columns={"perp": "s"})   # 🐋
    A = pd.concat([X, U, W], ignore_index=True)
    return {s: np.sort(g.t.to_numpy(np.int64)) for s, g in A.groupby("s")}


def simulate(col, rule):
    import fastbt as FB  # noqa: E402
    side, sl, hold = OUTS[col[2:]]
    D = pd.read_pickle("s219_feat.pkl")
    D = D[(D["T"] >= C0) & D[col].notna()].sort_values(["T", "s"])
    X = D[mask(D, rule)]
    rows = []
    for s, g in X.groupby("s"):
        if s not in FB.K:
            continue
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
    J = journals()
    R["jr"] = [bool(np.any(np.abs(J.get(s, np.zeros(0, np.int64)) - t) <= hold * 3600)) for s, t in zip(R.s, R.t)]
    return R


def report(col, rule):
    R = simulate(col, rule)
    months = (pd.Timestamp("2026-10-19", tz="UTC").timestamp() - C0) / (30.44 * DAY)
    m, t, n = ct(R.net, R.t); mh, th, _ = ct(R.hed, R.t); md, td, _ = ct(R.hed - R.pl, R.t)
    h1, h2 = R[R.t < MID].net.mean(), R[R.t >= MID].net.mean()
    hh1, hh2 = R[R.t < MID].hed.mean(), R[R.t >= MID].hed.mean()
    print(f"{col} | {rule}")
    print(f"  C: сделок {n} ({n / months:.1f} в месяц), без хеджа {m:+.2%} (t по неделям {t:+.1f}), половины {h1:+.2%} / {h2:+.2%}; "
          f"с хеджем {mh:+.2%} (t {th:+.1f}), половины {hh1:+.2%} / {hh2:+.2%}; сверх плацебо (с хеджем) {md:+.2%} (t {td:+.1f}); "
          f"стопов {R.stop.mean():.0%}; совпадает с журналами {R.jr.mean():.0%}")
    crit = [("≥ 20 в месяц", n / months >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
            ("сверх плацебо > 0", md > 0), ("с хеджем > 0", mh > 0), ("новая (≤ 50% совпадений)", R.jr.mean() <= 0.5)]
    print("  правило владельца и порог 4: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
    return R


if __name__ == "__main__":
    report(sys.argv[1], sys.argv[2])
