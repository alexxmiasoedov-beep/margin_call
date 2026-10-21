"""Корейский шорт со «счётом условий» (ажиотаж: пампов на рынке за 24 ч ≥ 16; BTC за сутки ≥ 0; цена выше максимума 7 дней;
покупки тейкеров в пампе ≤ 51%; доля Кореи ≥ 40%): месяцы, просадка, одновременные позиции для итоговых вариантов."""
import pickle
import numpy as np, pandas as pd
D = pd.read_pickle("s6/feat.pkl"); D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str)
Kr = D[D.kshare >= 0.2].copy()
Kr["score"] = ((Kr.pumps24 >= 16).astype(int) + (Kr.btc24 >= 0).astype(int) + (Kr.hi7 >= 0).astype(int)
               + (Kr.tb_pump <= 0.51).astype(int) + (Kr.kshare >= 0.4).astype(int))
K = pickle.load(open("s2/k2y.pkl", "rb"))
def exit_time(s, t, tp, sl, hold=192):
    a = K[s]; j = int(np.searchsorted(a["t"], t - 900)); e = float(a["c"][j]); end = min(j + hold, len(a["t"]) - 1)
    hi = a["h"][j + 1:end + 1] / e - 1; lo = a["l"][j + 1:end + 1] / e - 1
    b = np.flatnonzero(hi >= sl); g = np.flatnonzero(lo <= -tp); q = min(b[0] if len(b) else 10**9, g[0] if len(g) else 10**9)
    return a["t"][j + 1 + q] + 900 if q < 10**9 else a["t"][end] + 900
for nm, m, col in (("все корейские, 10/25 (как сейчас в журнале 🇰🇷)", Kr.score >= 0, "S_10_25"),
                   ("счёт ≥ 3, 7/20", Kr.score >= 3, "S_7_20"), ("счёт ≥ 4, 7/20", Kr.score >= 4, "S_7_20"),
                   ("счёт ≥ 3, 10/25", Kr.score >= 3, "S_10_25"), ("ажиотаж ≥ 16, 10/25", Kr.pumps24 >= 16, "S_10_25")):
    tp, sl = (int(x) / 100 for x in col.split("_")[1:])
    g = Kr[m].sort_values("t").copy(); u = g[col].values * 10; eq = np.cumsum(u); dd = (eq - np.maximum.accumulate(eq)).min()
    g["out"] = [exit_time(s, t, tp, sl) for s, t in zip(g.s, g.t)]
    ev = sorted([(t, 1) for t in g.t] + [(t, -1) for t in g.out]); cur = mx = 0
    for _, x in ev: cur += x; mx = max(mx, cur)
    mo = g.groupby(pd.to_datetime(g.t, unit="s").dt.strftime("%y-%m"))[col].sum() * 10
    streak = mxs = 0
    for v in g[col].values:
        streak = streak + 1 if v <= 0 else 0; mxs = max(mxs, streak)
    print(f"{nm}: {len(g)} сделок ({len(g) / 24.5:.0f} в месяц), винрейт {(g[col] > 0).mean():.1%}, {g[col].mean() * 100:+.2f}% на сделку, итог {u.sum():+.1f} USDT (1 × 10), "
          f"просадка {dd:+.1f}, месяцев в плюсе {(mo > 0).sum()}/{len(mo)}, одновременно до {mx}, самая длинная серия убытков {mxs}")
