"""«Слабый старт листинга», финальный вариант: через 24 ч после первой свечи нового фьючерса цена ≥ 25% ниже максимума первых суток →
шорт; тейк 30% / стоп 30% / 14 дней. По кварталам, против фона (шорт обычных монет), просадка, концентрация, исходы."""
import pickle, datetime
import numpy as np, pandas as pd
exec(open("s3/newlist2.py").read().split("rows = []")[0])
MSK = datetime.timezone(datetime.timedelta(hours=3))
def short2(s, j, tp, sl, hold):
    a = K[s]; e = float(a["c"][j]); n = len(a["t"]); end = min(j + hold, n - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    ks = np.flatnonzero(hi >= e * (1 + sl)); kt = np.flatnonzero(lo <= e * (1 - tp))
    q1 = ks[0] if len(ks) else 10**9; q2 = kt[0] if len(kt) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; pnl = -sl; how = "стоп"
    elif q2 < 10**9: q = j + 1 + q2; pnl = tp; how = "тейк"
    else: q = end; pnl = 1 - float(a["c"][end]) / e; how = "время"
    fd = fund(s, a["t"][j] + 900, a["t"][q] + 900)
    return pnl - 0.001 + fd, fd, how, a["t"][q] + 900
T = []
for s, a in K.items():
    if not (A <= a["t"][0] <= Bd) or len(a["t"]) < 96 * 16: continue
    j = 96; hmax = float(a["h"][:j + 1].max()); c = float(a["c"][j])
    if c <= hmax * 0.75:
        p, fd, how, tout = short2(s, j, 0.3, 0.3, 14 * 96); T.append(dict(s=s, t=a["t"][j] + 900, out=tout, p=p, fund=fd, how=how, drop=c / hmax - 1))
T = pd.DataFrame(T).sort_values("t"); T["q"] = pd.to_datetime(T.t, unit="s").dt.to_period("Q").astype(str)
u = T.p.values * 10; eq = np.cumsum(u); dd = (eq - np.maximum.accumulate(eq)).min()
ev = sorted([(t, 1) for t in T.t] + [(t, -1) for t in T.out]); cur = mx = 0
for _, x in ev: cur += x; mx = max(mx, cur)
print(f"сделок {len(T)}, монет {T.s.nunique()}, {T.p.mean() * 100:+.2f}% на сделку, в плюсе {(T.p > 0).mean():.0%}, итого {u.sum():+.1f} USDT (маржа 1 × 10), "
      f"просадка {dd:+.1f} USDT, одновременно до {mx}, фандинг {T.fund.mean() * 100:+.2f}% | исходы: " + ", ".join(f"{k} {v}" for k, v in T.how.value_counts().items()))
srt = T.sort_values("p", ascending=False); print(f"без 5 лучших сделок: {srt.p.iloc[5:].mean() * 100:+.2f}%; без 10: {srt.p.iloc[10:].mean() * 100:+.2f}%")
print("по кварталам:", " | ".join(f"{q}: {g.p.mean() * 100:+.1f}% ({len(g)})" for q, g in T.groupby("q")))
T.to_pickle("s3/newlist_trades.pkl")
