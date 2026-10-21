"""Лид-лаг Корея → Binance (месяц, 15 мин): свеча, где цена в Корее (Upbit/Bithumb, в $) выросла заметно сильнее, чем фьючерс Binance.
Догоняет ли Binance в следующие часы? И наоборот для падений."""
import pickle, re, datetime
import numpy as np
K = pickle.load(open("kaia/k15_all.pkl", "rb")); KO = pickle.load(open("mm2/korea.pkl", "rb"))
MSK = datetime.timezone(datetime.timedelta(hours=3))
T0 = datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp(); T1 = datetime.datetime(2026, 10, 18, tzinfo=MSK).timestamp()
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
rows = []
for s, k in K.items():
    c = strip(s)
    for ex in ("upbit", "bithumb"):
        a = KO[ex].get(c); fx = KO[ex].get("USDT")
        if a is None or fx is None or len(a) < 500: continue
        n = len(k); kc = np.full(n, np.nan); kv = np.zeros(n)
        idx = np.searchsorted(k[:, 0], a[:, 0]); ok = idx < n; ok[ok] &= k[idx[ok], 0] == a[ok, 0]
        fxv = np.interp(a[:, 0], fx[:, 0], fx[:, 4]); kc[idx[ok]] = a[ok, 4] / fxv[ok]; kv[idx[ok]] = a[ok, 5] / fxv[ok]
        bc = k[:, 4]
        for i in range(100, n - 97):
            te = k[i, 0] + 900
            if not (T0 <= te <= T1) or not (np.isfinite(kc[i]) and np.isfinite(kc[i - 1])): continue
            kr_r = kc[i] / kc[i - 1] - 1; b_r = bc[i] / bc[i - 1] - 1
            if abs(kr_r - b_r) < 0.03 or kv[i] < 20000: continue
            rows.append(dict(s=s, ex=ex, i=i, t=te, kr_r=kr_r, b_r=b_r, gap=kr_r - b_r,
                             f1=bc[i + 1] / bc[i] - 1, f4=bc[i + 4] / bc[i] - 1, f16=bc[i + 16] / bc[i] - 1, f96=bc[i + 96] / bc[i] - 1,
                             kf4=(kc[i + 4] / kc[i] - 1) if np.isfinite(kc[i + 4]) else np.nan))
print("случаев |Корея − Binance| ≥ 3% за свечу:", len(rows))
for lo, hi, lab in ((0.03, 0.05, "Корея обогнала на 3–5%"), (0.05, 0.10, "на 5–10%"), (0.10, 9, "на 10%+"), (-0.05, -0.03, "отстала на 3–5%"), (-0.10, -0.05, "отстала на 5–10%"), (-9, -0.10, "отстала на 10%+")):
    sel = [r for r in rows if lo <= r["gap"] < hi]
    if not sel: continue
    f = lambda key: np.nanmean([r[key] for r in sel]) * 100
    print(f"{lab:24s} {len(sel):5d} | Binance дальше: 15 мин {f('f1'):+.2f}%  1 ч {f('f4'):+.2f}%  4 ч {f('f16'):+.2f}%  24 ч {f('f96'):+.2f}% | Корея за 1 ч {f('kf4'):+.2f}%")
