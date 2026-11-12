"""Посекундный путь цены после начисления (лента сделок s23/agg + минутные свечи s23/k1m для выхода). Для каждого события:
p0 — последняя сделка до начисления; цена через k секунд — последняя сделка не позже T + k с. Шорт с входом через k секунд
и выходом через 15 / 30 / 45 мин (закрытие минуты): 1 − выход/вход − 0,1%. Запуск из папки с данными."""
import glob
import os
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT
from common23 import ct

E = pd.read_pickle("s23/fund_events.pkl").set_index(["s", "T"])
KS = (0, 1, 2, 3, 5, 10, 20, 30, 60, 120)
rows = []
for fn in glob.glob("s23/agg/*.npy"):
    s, T = os.path.basename(fn)[:-4].rsplit("_", 1); T = int(T)
    a = np.load(fn)
    if len(a) < 10 or (s, T) not in E.index:
        continue
    t, p = a[:, 0], a[:, 1]
    before = np.flatnonzero(t < T * 1000)
    if not len(before):
        continue
    p0 = p[before[-1]]
    r = E.loc[(s, T)]
    if isinstance(r, pd.DataFrame):
        r = r.iloc[0]
    row = dict(s=s, T=T, prev=r.prev, rate=r.rate, gap_next=r.gap_next)
    for k in KS:
        j = np.searchsorted(t, (T + k) * 1000, "right") - 1
        row[f"k{k}"] = p[j] / p0 - 1
    after = np.flatnonzero(t >= T * 1000)
    row["first_ms"] = (t[after[0]] - T * 1000) if len(after) else np.nan
    sell = (a[:, 3] == 1) & (t >= T * 1000) & (t < (T + 10) * 1000)          # покупатель — мейкер: агрессивная продажа
    buy = (a[:, 3] == 0) & (t >= T * 1000) & (t < (T + 10) * 1000)
    row["sell10"] = (a[sell, 1] * a[sell, 2]).sum(); row["buy10"] = (a[buy, 1] * a[buy, 2]).sum()
    m1 = f"s23/k1m/{s}_{pd.Timestamp(T, unit='s').strftime('%Y-%m-%d')}.npy"
    if os.path.exists(m1):
        b = np.load(m1)
        if len(b):
            tm = b[:, 0].astype(np.int64)
            for hold in (15, 30, 45):
                j = np.searchsorted(tm, T + (hold - 1) * 60)
                row[f"x{hold}"] = b[j, 4] / p0 - 1 if j < len(tm) and tm[j] == T + (hold - 1) * 60 else np.nan
    rows.append(row)
M = pd.DataFrame(rows)
M["bucket"] = pd.cut(M.prev * 100, [-100, -1, -0.3])
FEE = 0.001
print(f"событий с лентой сделок: {len(M)}")
for b, g in M.groupby("bucket", observed=True):
    print(f"\n== прошлая ставка {b}: {len(g)} событий, средняя ставка начисления {g.rate.mean() * 100:+.3f}%; "
          f"первая сделка после начисления через {g.first_ms.median():.0f} мс (медиана)")
    print("  путь цены к p0 (среднее / медиана), % по секундам: " +
          "  ".join(f"{k}с: {g[f'k{k}'].mean() * 100:+.2f}/{g[f'k{k}'].median() * 100:+.2f}" for k in KS))
    print(f"  агрессивные продажи / покупки за первые 10 с, тыс. $ (медиана): {g.sell10.median() / 1e3:.1f} / {g.buy10.median() / 1e3:.1f}")
    for k in (1, 2, 3, 5, 10, 20, 30, 60):
        res = []
        for hold in (15, 30, 45):
            ok = g[f"x{hold}"].notna() & (g.gap_next * 60 > hold + 1)
            x = (1 - (1 + g[f"x{hold}"]) / (1 + g[f"k{k}"]))[ok] - FEE
            m, t, n = ct(x, g["T"][ok])
            res.append(f"{hold} мин {m * 100:+.2f}% (t {t:+.1f}, n {n})")
        print(f"  шорт через {k:2d} с: " + " | ".join(res))
