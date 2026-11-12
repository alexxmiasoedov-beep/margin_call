"""Итоговое правило (Г9, медленный хвост после «отсечки» фандинга). Начисление с фактической ставкой ≤ порога (ставка
известна сразу после начисления) → шорт по закрытию k-й минуты после начисления, выход через min(55 мин, интервал − 5 мин)
по закрытию минуты (до следующего начисления — фандинг не платим); комиссия 0,1%. Разбивка: порог, задержка входа,
интервал, ликвидность (оборот за час до начисления), половины, кварталы; плацебо — тот же шорт в середине интервала того же
дня. Минутные свечи — s23/k1m (дни начислений с прошлой ставкой ≤ −0,3%). Запуск из папки с данными."""
import os
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT
from common23 import ct

E = pd.read_pickle("s23/fund_events.pkl")
cache = {}


def day(s, T):
    fn = f"s23/k1m/{s}_{pd.Timestamp(T, unit='s').strftime('%Y-%m-%d')}.npy"
    if fn not in cache:
        cache[fn] = np.load(fn) if os.path.exists(fn) else None
        if len(cache) > 3000:
            cache.pop(next(iter(cache)))
    return cache[fn]


FEE = 0.001
rows = []
for r in E[E.rate <= -0.005].itertuples():
    a = day(r.s, r.T)
    if a is None or not len(a):
        continue
    t = a[:, 0].astype(np.int64); c = a[:, 4]
    j = int(np.searchsorted(t, r.T))
    if j < 1 or j >= len(t) or t[j] != r.T:
        continue
    hold = int(min(55, r.gap_next * 60 - 5))
    row = dict(s=r.s, T=r.T, rate=r.rate, ih=r.ih, hold=hold, vol=r.vol_h)
    for k in (1, 2, 3, 5):
        ex = j + hold - 1
        if ex < len(t) and t[ex] == r.T + (hold - 1) * 60 and hold > k + 5:
            row[f"k{k}"] = 1 - c[ex] / c[j + k - 1] - FEE
    if r.ih >= 2:
        P = r.T + int(r.ih * 3600 / 2); k0 = int(np.searchsorted(t, P))
        if k0 + hold - 1 < len(t) and t[k0] == P:
            row["plac"] = 1 - c[k0 + hold - 1] / c[k0] - FEE
    rows.append(row)
R = pd.DataFrame(rows)
R.to_pickle("s23/final_trades.pkl")


def s(x, T):
    m, t, n = ct(x, T)
    h1, h2 = x[T < CUT], x[T >= CUT]
    return f"{m * 100:+.2f}% (t {t:+.1f}, n {n}; половины {h1.mean() * 100:+.2f} / {h2.mean() * 100:+.2f}; в плюсе {(x > 0).mean():.0%})"


for thr in (-0.01, -0.0075, -0.005):
    g = R[R.rate <= thr]
    print(f"\n== ставка начисления ≤ {thr * 100:.2f}%: событий {len(g)}, монет {g.s.nunique()}")
    for k in (1, 2, 3, 5):
        x = g[f"k{k}"].dropna(); print(f"  вход через {k} мин: {s(x, g.loc[x.index, 'T'])}")
    ok = g.k1.notna() & g.plac.notna()
    d = g.k1[ok] - g.plac[ok]; m, t, n = ct(d, g["T"][ok])
    print(f"  плацебо (середина интервала, те же события, n {n}): {g.plac[ok].mean() * 100:+.2f}% → разница {m * 100:+.2f} п. п. (t {t:+.1f})")
    for ih, x in g.groupby("ih"):
        if x.k1.notna().sum() >= 30:
            print(f"    интервал {ih:g} ч (держим {x.hold.median():.0f} мин): {s(x.k1.dropna(), x.loc[x.k1.notna(), 'T'])}")
    q = pd.qcut(g.vol, 3, labels=["низкий", "средний", "высокий"])
    for lv, x in g.groupby(q, observed=True):
        print(f"    оборот за час до начисления {lv} ({x.vol.min() / 1e6:.1f}–{x.vol.max() / 1e6:.1f} млн $): "
              f"{s(x.k1.dropna(), x.loc[x.k1.notna(), 'T'])}")
