"""🇰🇷⭐ со счётом из шести условий (пять прежних + воскресенье по UTC), порог ≥ 3; сравнение с прежним счётом из пяти."""
import pickle
import numpy as np, pandas as pd
D = pd.read_pickle("s6/feat.pkl"); D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str)
Kr = D[D.kshare >= 0.2].copy()
Kr["s5"] = ((Kr.pumps24 >= 16).astype(int) + (Kr.btc24 >= 0).astype(int) + (Kr.hi7 >= 0).astype(int) + (Kr.tb_pump <= 0.51).astype(int) + (Kr.kshare >= 0.4).astype(int))
Kr["s6"] = Kr.s5 + (Kr.dow == 6).astype(int)
K = pickle.load(open("s2/k2y.pkl", "rb"))
def exit_time(s, t, tp, sl, hold=192):
    a = K[s]; j = int(np.searchsorted(a["t"], t - 900)); e = float(a["c"][j]); end = min(j + hold, len(a["t"]) - 1)
    hi = a["h"][j + 1:end + 1] / e - 1; lo = a["l"][j + 1:end + 1] / e - 1
    b = np.flatnonzero(hi >= sl); g = np.flatnonzero(lo <= -tp); q = min(b[0] if len(b) else 10**9, g[0] if len(g) else 10**9)
    return a["t"][j + 1 + q] + 900 if q < 10**9 else a["t"][end] + 900
for nm, m in (("счёт из 5 ≥ 3 (как сейчас)", Kr.s5 >= 3), ("счёт из 6 ≥ 3 (+ воскресенье)", Kr.s6 >= 3), ("добавятся: воскресенье при счёте из 5 = 2", (Kr.s5 == 2) & (Kr.dow == 6))):
    g = Kr[m].sort_values("t").copy(); col = "S_7_20"; u = g[col].values * 10; eq = np.cumsum(u); dd = (eq - np.maximum.accumulate(eq)).min()
    g["out"] = [exit_time(s, t, 0.07, 0.20) for s, t in zip(g.s, g.t)]
    ev = sorted([(t, 1) for t in g.t] + [(t, -1) for t in g.out]); cur = mx = 0
    for _, x in ev: cur += x; mx = max(mx, cur)
    mo = g.groupby(pd.to_datetime(g.t, unit="s").dt.strftime("%y-%m"))[col].sum(); qm = g.groupby("q")[col].mean()
    streak = mxs = 0
    for v in g[col].values: streak = streak + 1 if v <= 0 else 0; mxs = max(mxs, streak)
    y1 = g[g.y == 1]; y2 = g[g.y == 2]
    print(f"{nm}: {len(g)} сделок ({len(g) / 24.5:.0f} в месяц), WR {(g[col] > 0).mean():.1%}, {g[col].mean() * 100:+.2f}% "
          f"(1-й {(y1[col] > 0).mean():.1%} {y1[col].mean() * 100:+.2f}%, 2-й {(y2[col] > 0).mean():.1%} {y2[col].mean() * 100:+.2f}%), итог {u.sum():+.1f} USDT, "
          f"просадка {dd:+.1f}, месяцев в плюсе {(mo > 0).sum()}/{len(mo)}, кварталов {(qm > 0).sum()}/{len(qm)}, одновременно до {mx}, серия убытков {mxs}")
