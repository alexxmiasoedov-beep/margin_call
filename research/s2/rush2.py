"""Набег турецкой розницы: пересечение с корейским шортом, монеты вне Кореи, устойчивость к порогам и выходам."""
import pickle, re, glob, os, datetime
import numpy as np, pandas as pd
exec(open("s2/rush.py").read().split('if __name__ == "__main__":')[0])
R = pickle.load(open("mm2/bt2y.pkl", "rb")); KR = {}
for r in R:
    if r["korea"] and r["share"] >= 0.2: KR.setdefault(r["s"], []).append(r["t_in"])
krmk = {os.path.basename(f).split("_")[1] for f in glob.glob("mm2/korea2y/*_*.npy")} - {"USDT"}
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
def frame(ev, tp=0.1, sl=0.15, hold=96):
    d = pd.DataFrame([(s, *trade(s, j, tp, sl, hold)) for s, j in ev], columns=["s", "t", "p", "fund"])
    d["near_kr"] = [any(abs(T - x) <= 86400 for x in KR.get(s, [])) for s, T in zip(d.s, d.t)]
    d["in_kr"] = [strip(s) in krmk for s in d.s]; d["q"] = pd.to_datetime(d.t, unit="s").dt.to_period("Q").astype(str); return d
def line(name, d):
    if not len(d): print(f"{name:58s} нет"); return
    qm = d.groupby("q").p.mean()
    print(f"{name:58s} {len(d):5d} | {d.p.mean() * 100:+.2f}% | плюс {(d.p > 0).mean():.0%} | кв.+ {(qm > 0).sum()}/{len(qm)} | " + " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items()))
ev = events(0.10, 3, 0.10, 1.0); d = frame(ev)
line("основной: доля ≥ 10%, ×3, рост за 4 ч ≥ 10%", d)
line("  без корейского шорта рядом (±24 ч)", d[~d.near_kr]); line("  рядом корейский шорт", d[d.near_kr])
line("  монеты, которых нет в Корее", d[~d.in_kr]); line("  монеты, которые есть в Корее", d[d.in_kr])
print()
for S, M, lo in ((0.07, 3, 0.1), (0.1, 2, 0.1), (0.1, 3, 0.07), (0.1, 3, 0.15), (0.15, 3, 0.1), (0.1, 4, 0.1)):
    line(f"доля ≥ {S:.0%}, ×{M}, рост ≥ {lo:.0%}", frame(events(S, M, lo, 1.0)))
print()
for tp, sl, hold in ((0.1, 0.15, 96), (0.1, 0.25, 192), (0.15, 0.25, 192), (0.07, 0.15, 96), (0.15, 0.15, 96), (0.2, 0.2, 192)):
    line(f"выход тейк {tp:.0%} / стоп {sl:.0%} / {hold // 4} ч", frame(ev, tp, sl, hold))
pickle.dump(d, open("s2/rush_main.pkl", "wb"))
