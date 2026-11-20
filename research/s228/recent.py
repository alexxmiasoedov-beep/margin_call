"""s228, после расчёта (для понимания, не для решения): вне канала — монеты, бывшие в канале за прошлые 24 ч, против монет,
которых не было в канале 7 сут. k ≥ 3 по 23 правилам, честные сделки, шорт 4 ч с хеджем альтов, t по неделям.
Запуск из /home/user/mc_data после evaluate.py: python3 <repo>/research/s228/recent.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evaluate as E  # noqa: E402

H, DAY = 3600, 86400


def main():
    D = pd.read_pickle("s228/feat.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    P = pd.read_pickle("s224/work/s21/panel.pkl")
    hrs = {s: np.sort(g["T"].to_numpy(np.int64)) for s, g in P.groupby("s")}
    T = D["T"].to_numpy(np.int64); s = D.s.astype(str).to_numpy()
    last = np.full(len(D), -1e18)
    for c, ix in pd.Series(np.arange(len(D))).groupby(s).groups.items():
        h = hrs.get(c)
        if h is None:
            continue
        ix = np.asarray(ix); k = np.searchsorted(h, T[ix], "left") - 1       # последний час в канале строго до T
        last[ix] = np.where(k >= 0, h[np.maximum(k, 0)], -1e18)
    gap = T - last
    y = D.y.to_numpy(float); end = D.u_e.to_numpy(float)
    votes = np.zeros(len(D), np.int32)
    for r in E.RULES:
        votes += np.logical_and.reduce([E.cond(D, f, op, q) for f, op, q in r])
    out = ~D.inch.to_numpy(bool)
    for name, g in (("вне канала, в канале за 24 ч", out & (gap <= DAY)), ("вне канала, не было 7 сут", out & (gap > 7 * DAY))):
        for sel_name, sel in (("k ≥ 3", votes >= 3), ("все", np.ones(len(D), bool))):
            tk = E.honest(sel & g, D, y, end)
            for seg, lo, hi in E.SEG[1:]:
                m = (T[tk] >= lo) & (T[tk] < hi)
                mean, t, n = E.ct(y[tk][m], T[tk][m])
                print(f"{name:30s} {sel_name:6s} {seg:6s} {n:6d} сделок {mean:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    main()
