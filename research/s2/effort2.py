"""«Усилие без результата»: устойчивость к порогам, пересечение с корейским шортом, доля монет из Кореи."""
import pickle, re
import numpy as np, pandas as pd
exec(open("s2/effort.py").read().split("for X in (3, 4, 6):")[0])
R = pickle.load(open("mm2/bt2y.pkl", "rb"))
KR = {}
for r in R:
    if r["korea"] and r["share"] >= 0.2: KR.setdefault(r["s"], []).append(r["t_in"])
import glob, os
krmk = set()
for f in glob.glob("mm2/korea2y/*_*.npy"):
    c = os.path.basename(f).split("_")[1]
    if c != "USDT": krmk.add(c)
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
def tag(ev):
    out = []
    for s, T in ev:
        near = any(abs(T - x) <= 86400 for x in KR.get(s, []))
        out.append((s, T, near, strip(s) in krmk))
    return out
def rep2(name, ev, tp=0.1, sl=0.15, hold=24):
    tg = tag(ev); rows = []
    for s, T, near, inkr in tg:
        r = trade(s, T, "short", tp, sl, hold)
        if r: rows.append((T, r[0], near, inkr))
    a = pd.DataFrame(rows, columns=["T", "p", "near", "inkr"]); a["q"] = pd.to_datetime(a["T"], unit="s").dt.to_period("Q").astype(str)
    qm = a.groupby("q").p.mean()
    f = lambda m: f"{a.loc[m, 'p'].mean() * 100:+.2f}% ({int(m.sum())})" if m.any() else "— (0)"
    print(f"{name:34s} {len(a):4d} | {a.p.mean() * 100:+.2f}% | кв.+ {(qm > 0).sum()}/{len(qm)} | рядом корейский шорт: {f(a.near)}, без него: {f(~a.near)} | "
          f"монета есть в Корее: {f(a.inkr)}, нет: {f(~a.inkr)}")
for X in (8, 10, 15):
    for lo, hi in ((0.05, 0.15), (0.1, 0.25), (0.15, 0.3), (0.25, 0.5)):
        rep2(f"объём ≥ {X}×, рост {lo:.0%}–{hi:.0%}", events((P.volr >= X) & (P.r24 > lo) & (P.r24 <= hi)))
