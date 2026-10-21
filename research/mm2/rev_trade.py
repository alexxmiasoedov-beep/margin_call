"""Разворот после пампа как СДЕЛКА: шорт в закрытии 15-мин свечи момента, тейк 15% / стоп 15% (симметрично — волатильность
сама по себе не даёт перекоса), до 24 ч; если в одной свече и тейк, и стоп — считаем стоп. Какие признаки дают перекос
в сторону тейка — и сколько это денег (средний итог в верхней и нижней пятой части признака, по половинам месяца)."""
import pickle, datetime, os, sys
import numpy as np, scipy.stats as st
MSK = datetime.timezone(datetime.timedelta(hours=3))
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
F = pickle.load(open("mm2/rev_feats.pkl", "rb")); R = {(r["s"], r["i"]): r for r in pickle.load(open("mm2/rev_moments.pkl", "rb"))}
TP, SL, H = 0.15, 0.15, 96
def short(s, i, tp=TP, sl=SL, hold=H):
    k = K[s]; e = k[i, 4]
    for j in range(i + 1, min(i + 1 + hold, len(k))):
        if k[j, 2] >= e * (1 + sl): return -sl, "стоп"
        if k[j, 3] <= e * (1 - tp): return tp, "тейк"
    return 1 - k[min(i + hold, len(k) - 1), 4] / e, "время"
for f in F:
    f.update({k: v for k, v in R[(f["s"], f["i"])].items() if k in ("since_h", "pump_gain", "gain_now", "from_peak", "h_since_peak", "ev")})
    f["pnl"], f["exit"] = short(f["s"], f["i"]); f["pnl"] -= 0.001
pickle.dump(F, open("mm2/rev_feats_pnl.pkl", "wb"))
MID = datetime.datetime(2026, 10, 4, tzinfo=MSK).timestamp()
P = np.array([f["pnl"] for f in F]); W = np.array([f["exit"] == "тейк" for f in F]); L = np.array([f["exit"] == "стоп" for f in F])
H1 = np.array([f["t0"] < MID for f in F])
print(f"моментов {len(F)} | шорт 15/15 24ч: средний итог {P.mean():+.2%} | тейк {W.mean():.0%} стоп {L.mean():.0%} время {1 - W.mean() - L.mean():.0%}")
keys = sorted({k for r in F for k in r if k not in ("g", "s", "i", "t0", "ev", "pnl", "exit")})
out = []
for k in keys:
    v = np.array([f.get(k, np.nan) for f in F], float); ok = np.isfinite(v)
    if ok.sum() < 2000: continue
    a, b = v[ok & W], v[ok & L]
    if len(a) < 50 or len(b) < 50: continue
    rk = st.rankdata(np.concatenate([a, b])); au = (rk[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))
    q1, q4 = np.nanpercentile(v[ok], [20, 80]); res = []
    for half in (H1, ~H1):
        m = ok & half; hi = P[m & (v >= q4)].mean(); lo = P[m & (v <= q1)].mean(); res.append((hi, lo))
    out.append((k, ok.sum(), au, q1, q4, P[ok & (v >= q4)].mean(), P[ok & (v <= q1)].mean(), res))
print(f"{'признак':16s} {'n':>6s} AUC тейк/стоп | порог 20% / 80% | итог при признаке ≥80%-ке / ≤20%-ке | 1-я половина | 2-я половина")
for k, n, au, q1, q4, hi, lo, res in sorted(out, key=lambda x: -abs(x[2] - 0.5)):
    print(f"{k:16s} {n:6d}  {au:.2f} | {q1:9.4g} {q4:9.4g} | {hi:+.2%} {lo:+.2%} | {res[0][0]:+.2%} {res[0][1]:+.2%} | {res[1][0]:+.2%} {res[1][1]:+.2%}")
