"""Пробуждение спящей монеты против корейского шорта и турецкого набега: пересечение (та же монета ±24 ч) и итог без пересечений."""
import pickle, datetime, re, glob, os
import numpy as np, pandas as pd
exec(open("s2/explode.py").read().split('if __name__ == "__main__":')[0])
CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
R = pickle.load(open("mm2/bt2y.pkl", "rb")); RT = pickle.load(open("s2/rush_trades.pkl", "rb"))
KR = {}; TRS = {}
for r in R:
    if r["korea"] and r["share"] >= 0.2: KR.setdefault(r["s"], []).append(r["t_in"])
for s, t in zip(RT.s, RT.t): TRS.setdefault(s, []).append(t)
near = lambda D, s, T: any(abs(T - x) <= 86400 for x in D.get(s, []))
for X, lo, hi in ((20, 0.1, 1.0), (50, 0.1, 0.5), (80, 0.05, 0.5)):
    d = table(events(X, lo, hi), 0.1, 0.15, 96)
    d["kr"] = [near(KR, s, t) for s, t in zip(d.s, d.t)]; d["tr"] = [near(TRS, s, t) for s, t in zip(d.s, d.t)]
    alone = d[~d.kr & ~d.tr]; qm = alone.groupby("q").p.mean()
    print(f"объём ≥ {X}×, рост {lo:.0%}–{hi:.0%}: {len(d)} сделок, {d.p.mean() * 100:+.2f}% | рядом корейский {d.kr.mean():.0%}, турецкий {d.tr.mean():.0%} | "
          f"без них {len(alone)}: {alone.p.mean() * 100:+.2f}% (1-й год {alone[alone.t < CUT].p.mean() * 100:+.2f}, 2-й {alone[alone.t >= CUT].p.mean() * 100:+.2f}), "
          f"кв.+ {(qm > 0).sum()}/{len(qm)}")
