"""Смена интервала фандинга Binance (8→4→1 ч при упоре ставки в предел): что с ценой после."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
rows = []
for s, fr in F.items():
    if s not in K: continue
    a = K[s]; t = a["t"]; c = a["c"].astype(np.float64)
    ft = np.round(fr[:, 0].astype(np.float64) / 3600) * 3600; iv = fr[:, 1]; r = fr[:, 2].astype(np.float64)
    for i in np.flatnonzero(np.diff(iv) != 0) + 1:
        t1 = ft[i]; j = np.searchsorted(t, t1 - 900)  # свеча, закрывающаяся в t1
        if j >= len(t) or t[j] != t1 - 900 or j < 96 * 3: continue
        e = c[j]; fw = {}
        for nm, hh in (("4h", 16), ("24h", 96), ("3d", 288), ("7d", 672)):
            fw[nm] = c[j + hh] / e - 1 if j + hh < len(t) else np.nan
        # фандинг, который получил бы шорт за 3 дня
        m = (ft > t1) & (ft <= t1 + 3 * 86400); f3 = r[m].sum()
        rows.append(dict(s=s, t=t1, old=iv[i - 1], new=iv[i], rate=r[i - 1], rate8=r[max(0, i - 6):i].sum(), past24=e / c[j - 96] - 1, past3d=e / c[j - 288] - 1, f3=f3, **fw))
D = pd.DataFrame(rows); D["y"] = np.where(D.t < CUT, 1, 2); D["kind"] = np.where(D.new < D.old, "короче", "длиннее")
D.to_pickle("s4/fiv.pkl")
for kind, g in D.groupby("kind"):
    print(f"\n{kind}: {len(g)}")
    for sg, gg in ((">0", g[g.rate > 0]), ("<0", g[g.rate < 0]), ("=0", g[g.rate == 0])):
        if not len(gg): continue
        line = f"  ставка {sg}: {len(gg):4d} | прошлое 24ч {gg.past24.median()*100:+.1f}% 3д {gg.past3d.median()*100:+.1f}% | вперёд (медиана / среднее): "
        line += " ".join(f"{k} {gg[k].median()*100:+.1f}/{gg[k].mean()*100:+.1f}" for k in ("4h", "24h", "3d", "7d"))
        line += f" | фандинг шорту за 3д {gg.f3.mean()*100:+.2f}%"
        print(line)
        for y in (1, 2):
            q = gg[gg.y == y]
            print(f"     год {y}: {len(q):4d} " + " ".join(f"{k} {q[k].median()*100:+.1f}/{q[k].mean()*100:+.1f}" for k in ("24h", "3d", "7d")))
