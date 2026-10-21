"""Набег турецкой розницы: подбор порогов только на 1-м году → проверка на 2-м; помесячно, просадка, позиции, концентрация по монетам."""
import pickle, datetime, itertools
import numpy as np, pandas as pd
exec(open("s2/rush.py").read().split('if __name__ == "__main__":')[0])
MSK = datetime.timezone(datetime.timedelta(hours=3)); CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
grid = []
for S, M, lo in itertools.product((0.05, 0.07, 0.1, 0.15, 0.2), (2, 3, 4, 5), (0.05, 0.07, 0.1, 0.15)):
    ev = events(S, M, lo, 1.0)
    rows = [trade(s, j, 0.1, 0.15, 96) for s, j in ev]
    a = np.array(rows) if rows else np.zeros((0, 3))
    y1, y2 = a[a[:, 0] < CUT, 1], a[a[:, 0] >= CUT, 1]
    if len(y1) >= 100: grid.append((S, M, lo, len(y1), y1.mean(), len(y2), y2.mean() if len(y2) else np.nan))
G = pd.DataFrame(grid, columns=["S", "M", "lo", "n1", "y1", "n2", "y2"]).sort_values("y1", ascending=False)
print("лучшие 8 по 1-му году (≥ 100 сделок) и их 2-й год:"); print((G.head(8).assign(y1=lambda d: (d.y1 * 100).round(2), y2=lambda d: (d.y2 * 100).round(2))).to_string(index=False))
print(f"\nвсе {len(G)} вариантов сетки: 2-й год в плюсе у {(G.y2 > 0).sum()}; средний итог 2-го года {G.y2.mean() * 100:+.2f}%; корреляция рангов 1-й/2-й год {G.y1.rank().corr(G.y2.rank()):.2f}")
ev = events(0.10, 3, 0.10, 1.0)
T = pd.DataFrame([(s, *trade(s, j, 0.1, 0.15, 96), j) for s, j in ev], columns=["s", "t", "p", "fund", "j"]).sort_values("t")
T["out"] = [K[s]["t"][min(j + 96, len(K[s]["t"]) - 1)] + 900 for s, j in zip(T.s, T.j)]
u = T.p.values * 10; eq = np.cumsum(u); dd = (eq - np.maximum.accumulate(eq)).min()
evs = sorted([(t, 1) for t in T.t] + [(t, -1) for t in T.out]); cur = mx = 0
for _, x in evs: cur += x; mx = max(mx, cur)
print(f"\nосновное правило: {len(T)} сделок, {u.sum():+.1f} USDT (маржа 1 × 10), худшая просадка {dd:+.1f} USDT, одновременно до {mx} позиций (оценка сверху — выход по времени)")
by = T.groupby("s").p.sum().sort_values(ascending=False)
print(f"монет {len(by)}, в плюсе {(by > 0).sum()}; 10 лучших монет дают {by.head(10).sum() / T.p.sum():.0%} суммы; без них {T[~T.s.isin(by.head(10).index)].p.mean() * 100:+.2f}% на сделку")
T["m"] = pd.to_datetime(T.t, unit="s").dt.tz_localize("UTC").dt.tz_convert(MSK).dt.strftime("%Y-%m")
mm = T.groupby("m").p.agg(["size", "sum", "mean"]); mm["sum"] *= 10; mm["mean"] *= 100
print(f"месяцев в плюсе: {(mm['sum'] > 0).sum()} из {len(mm)}"); print(mm.round(2).T.to_string())
pickle.dump(T, open("s2/rush_trades.pkl", "wb"))
