"""Цикл начисления фандинга на минутных свечах (s23/k1m): насколько быстро идёт падение после начисления и успевает ли
бот. Событие — начисление с прошлой ставкой ≤ −0,3% (s23/fund_events.pkl). p0 — закрытие минуты, кончающейся в момент
начисления; o0 — первая цена после начисления (открытие минуты T). Путь цены к p0 по минутам. Сделки (комиссия 0,1%):
  лонг за k мин до начисления → выход по o0 / через 1 / 2 мин (+ полученный фандинг);
  шорт после начисления: вход по o0 / через 1 / 2 / 5 мин → выход через 15 / 30 / 45 мин (раньше следующего начисления).
Запуск из папки с данными."""
import os
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT
from common23 import ct

E = pd.read_pickle("s23/fund_events.pkl")
E = E[E.prev <= -0.003].reset_index(drop=True)
cache = {}


def day(s, d):
    k = (s, d)
    if k not in cache:
        fn = f"s23/k1m/{s}_{d}.npy"
        cache[k] = np.load(fn) if os.path.exists(fn) else np.zeros((0, 7))
        if len(cache) > 400:
            cache.pop(next(iter(cache)))
    return cache[k]


rows = []
for r in E.itertuples():
    T = int(r.T); d = pd.Timestamp(T, unit="s")
    parts = [day(r.s, (d - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))] if d.hour < 3 else []
    parts.append(day(r.s, d.strftime("%Y-%m-%d")))
    a = np.concatenate([p for p in parts if len(p)]) if any(len(p) for p in parts) else np.zeros((0, 7))
    if not len(a):
        continue
    t = a[:, 0].astype(np.int64)
    j = int(np.searchsorted(t, T))
    if j < 121 or j + 60 >= len(t) or t[j] != T or t[j - 121] != T - 121 * 60 or t[j + 60] != T + 60 * 60:
        continue
    c, o = a[:, 4], a[:, 1]
    p0, o0 = c[j - 1], o[j]
    row = dict(s=r.s, T=T, rate=r.rate, prev=r.prev, gap_next=r.gap_next, ih=r.ih, gap0=o0 / p0 - 1)
    for k in (15, 30, 60, 120):
        row[f"in{k}"] = c[j - 1 - k]                     # цена входа за k мин до начисления
    for m in range(0, 61):
        row[f"c{m}"] = c[j - 1 + m] / p0 - 1            # c0 = 0; cm — закрытие m-й минуты после начисления
    row["o0r"] = 0.0
    row["p0"] = p0
    rows.append(row)
M = pd.DataFrame(rows)
M.to_pickle("s23/fund_1m.pkl")
print(f"событий с минутными свечами: {len(M)} из {len(E)}")
M["bucket"] = pd.cut(M.prev * 100, [-100, -1, -0.3])
FEE = 0.001


def st(x, T):
    m, t, n = ct(x, T)
    h1, h2 = x[T < CUT], x[T >= CUT]
    return f"{m * 100:+.3f}% (t {t:+.1f}; {h1.mean() * 100:+.3f} / {h2.mean() * 100:+.3f})"


for b, g in M.groupby("bucket", observed=True):
    print(f"\n== прошлая ставка {b}: событий {len(g)}, средняя ставка начисления {g.rate.mean() * 100:+.3f}%")
    path = g[[f"c{m}" for m in range(0, 61)]].mean() * 100
    print(f"  первая цена после начисления к p0: {g.gap0.mean() * 100:+.3f}% (медиана {g.gap0.median() * 100:+.3f}%)")
    print("  путь после начисления, % к p0 (минуты 1,2,3,5,10,15,20,30,45,60): " +
          " ".join(f"{path[f'c{m}']:+.2f}" for m in (1, 2, 3, 5, 10, 15, 20, 30, 45, 60)))
    pre = {k: (g.p0 / g[f"in{k}"] - 1).mean() * 100 for k in (15, 30, 60, 120)}
    print("  рост до начисления, % (за 120, 60, 30, 15 мин): " + " ".join(f"{pre[k]:+.2f}" for k in (120, 60, 30, 15)))
    for k in (15, 30, 60, 120):
        ex = {nm: (1 + g.gap0 if nm == "o0" else 1 + g[f"c{int(nm[1:])}"]) for nm in ("o0", "c1", "c2")}
        print(f"  лонг за {k:3d} мин, выход " + " | ".join(
            f"{nm}: {st(g.p0 * ex[nm] / g[f'in{k}'] - 1 - g.rate - FEE, g['T'])}" for nm in ex))
    for ent in ("o0", "c1", "c2", "c5"):
        e0 = g.gap0 if ent == "o0" else g[ent]
        res = []
        for hold in (15, 30, 45):
            ok = g.gap_next * 60 > hold + 1
            x = (1 - (1 + g[f"c{hold}"]) / (1 + e0))[ok] - FEE        # линейный шорт USDT-M: 1 − выход/вход
            res.append(f"{hold} мин: {st(x, g['T'][ok])}")
        print(f"  шорт с входом {ent}: " + " | ".join(res))
