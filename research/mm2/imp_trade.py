"""Импульс из покоя как СДЕЛКА: лонг в закрытии импульсной 15-мин свечи. Варианты: 10/5 за 2 ч и 15/7 за 6 ч (стоп первым в общей свече).
Какие признаки отличают импульсы, которые продолжились, — и сколько это денег (верхняя / нижняя пятая часть признака по половинам месяца)."""
import pickle, datetime
import numpy as np, scipy.stats as st
MSK = datetime.timezone(datetime.timedelta(hours=3))
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
F = pickle.load(open("mm2/imp_feats.pkl", "rb"))
def lng(s, i, tp, sl, hold):
    k = K[s]; e = k[i, 4]
    for j in range(i + 1, min(i + 1 + hold, len(k))):
        if k[j, 3] <= e * (1 - sl): return -sl
        if k[j, 2] >= e * (1 + tp): return tp
    return k[min(i + hold, len(k) - 1), 4] / e - 1
for f in F:
    f["pnl"] = lng(f["s"], f["i"], 0.10, 0.05, 8) - 0.001; f["pnl2"] = lng(f["s"], f["i"], 0.15, 0.07, 24) - 0.001
pickle.dump(F, open("mm2/imp_feats_pnl.pkl", "wb"))
MID = datetime.datetime(2026, 10, 4, tzinfo=MSK).timestamp()
H1 = np.array([f["t0"] < MID for f in F])
for col in ("pnl", "pnl2"):
    P = np.array([f[col] for f in F]); W = P > 0
    print(f"\n=== {'10/5 за 2 ч' if col == 'pnl' else '15/7 за 6 ч'}: импульсов {len(F)}, средний итог {P.mean():+.2%}, в плюсе {W.mean():.0%}")
    keys = sorted({k for r in F for k in r if k not in ("g", "s", "i", "t0", "pnl", "pnl2")})
    out = []
    for k in keys:
        v = np.array([f.get(k, np.nan) for f in F], float); ok = np.isfinite(v)
        if ok.sum() < 300: continue
        a, b = v[ok & W], v[ok & ~W]
        rk = st.rankdata(np.concatenate([a, b])); au = (rk[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))
        q1, q4 = np.nanpercentile(v[ok], [20, 80]); res = []
        for half in (H1, ~H1):
            m = ok & half; res.append((P[m & (v >= q4)].mean(), P[m & (v <= q1)].mean()))
        out.append((k, ok.sum(), au, q1, q4, P[ok & (v >= q4)].mean(), P[ok & (v <= q1)].mean(), res))
    print(f"{'признак':16s} {'n':>5s} AUC | порог 20% / 80% | итог ≥80% / ≤20% | 1-я половина | 2-я половина")
    for k, n, au, q1, q4, hi, lo, res in sorted(out, key=lambda x: -abs(x[2] - 0.5))[:35]:
        print(f"{k:16s} {n:5d} {au:.2f} | {q1:9.4g} {q4:9.4g} | {hi:+.2%} {lo:+.2%} | {res[0][0]:+.2%} {res[0][1]:+.2%} | {res[1][0]:+.2%} {res[1][1]:+.2%}")
