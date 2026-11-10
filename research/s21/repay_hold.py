"""Срок удержания для журнала ↩️. По s21 (borrow_study.py) монеты канала после всплеска отдачи на сильном ходе цены
отстают от рынка не за 1–2 суток, а до 7 суток (+4…+6% к рынку за 168 ч). Здесь — правило ↩️ ровно как в боте
(scanner.repay_rule, как «резкое — цепочка» в s9/repay_clean.py): монета в канале ≥ 6 ч, отдача за час ×2 и +20 тыс. $,
первый всплеск ×1,5 и +10 тыс. $ за час, цена за сутки ±10%+, вход на закрытии 15-мин свечи поста; новая сделка по монете —
когда прежняя закрыта и с её входа прошло ≥ 24 ч. Выходы — текущий (тейк 10 / стоп 25 / 48 ч) против более долгих.
Сделки — s15/common.trade (стоп с проскальзыванием 0,2%, комиссия 0,1%, фактический фандинг), хедж BTC — как у 🏦.
Запуск из папки с данными: python3 s21/repay_hold.py"""
import os
import pickle
import sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, HERE)
from common import BAR, K, fut_of, trade
from borrow_trades import btc_leg

G = pickle.load(open("s7/margin.pkl", "rb"))["G"]
CUT = 1764547200                     # 01.12.2025 — граница половин, как в s9


def signals():
    rows = []
    for c0, arr in G.items():
        s, _ = fut_of(c0)
        if s is None:
            continue
        t = K[s]["t"]; c = K[s]["c"].astype(float)
        tt, rep = arr[:, 0], arr[:, 2]
        st_idx = np.r_[0, np.flatnonzero(np.diff(tt) > 1800) + 1]; ends = np.r_[st_idx[1:] - 1, len(tt) - 1]
        for st, en in zip(st_idx, ends):
            last_chain = -1e18
            for i in range(st, en + 1):
                run = (tt[i] - tt[st]) / 3600
                k = np.searchsorted(tt, tt[i] - 3600, "right") - 1
                if k < st or tt[i] - tt[k] > 75 * 60:
                    continue
                x = rep[i] / max(rep[k], 1.0); dr = rep[i] - rep[k]
                if not (x >= 1.5 and dr >= 10e3):
                    continue
                chain = run >= 2 and tt[i] - last_chain >= 3600
                if chain:
                    last_chain = tt[i]
                if not chain or run < 6 or x < 2 or dr < 20e3:
                    continue
                j = int(np.searchsorted(t, tt[i], "right") - 1)
                if j < 96 or j >= len(t) - 2:
                    continue
                mv = c[j] / c[j - 96] - 1
                if abs(mv) >= 0.10:
                    rows.append((s, j, tt[i], float(t[j]) + BAR, mv))
    C = pd.DataFrame(rows, columns=["s", "j", "t", "T", "mv"]).sort_values("t")
    return C.drop_duplicates(["s", "j"]).reset_index(drop=True)


def journal(C, tp, sl, hold):
    out, last = [], {}
    for r in C.itertuples():
        lo, lc = last.get(r.s, (-1e18, -1e18))
        if r.T - lo < 86400 or r.T < lc:
            continue
        x = trade(r.s, r.j, tp=tp, sl=sl, hold_h=hold)
        if x is None:
            continue
        t1 = float(K[r.s]["t"][r.j + x["bars"]]) + BAR
        last[r.s] = (r.T, t1)
        out.append(dict(s=r.s, T=r.T, t1=t1, mv=r.mv, net=x["net"], why=x["why"], hedged=x["net"] + btc_leg(r.T, t1)))
    return pd.DataFrame(out)


def show(R, name):
    x = R.net; h1, h2 = x[R["T"] < CUT], x[R["T"] >= CUT]
    eq = (x * 10).cumsum(); dd = (eq - eq.cummax()).min()
    mo = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("M")).net.sum()
    q = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("Q")).net.mean()
    ev = sorted([(a, 1) for a in R["T"]] + [(b, -1) for b in R.t1]); cur = mx = 0
    for _, d in ev:
        cur += d; mx = max(mx, cur)
    print(f"  {name:24s} n={len(R)}, в плюсе {(x > 0).mean():.0%}, {x.mean() * 100:+.2f}% на сделку (t {x.mean() / x.std() * np.sqrt(len(x)):+.1f}), "
          f"итог {x.sum() * 10:+.1f} USDT (1 × 10), просадка {dd:.1f}, стопов {(R.why == 'стоп').mean():.0%}, хедж BTC "
          f"{R.hedged.mean() * 100:+.2f}% | половины {h1.mean() * 100:+.2f}% ({len(h1)}) / {h2.mean() * 100:+.2f}% ({len(h2)}) | "
          f"после роста {x[R.mv > 0].mean() * 100:+.2f}%, после падения {x[R.mv < 0].mean() * 100:+.2f}% | месяцев в плюсе "
          f"{(mo > 0).sum()}/{len(mo)}, кварталов {(q > 0).sum()}/{len(q)} | одновременно до {mx}")


if __name__ == "__main__":
    C = signals()
    print(f"сигналов ↩️ (первый пост свечи): {len(C)}, {pd.to_datetime(C.t.min(), unit='s').date()} — "
          f"{pd.to_datetime(C.t.max(), unit='s').date()}")
    for nm, tp, sl, hold in (("тейк 10 / стоп 25 / 48 ч", 0.10, 0.25, 48), ("тейк 10 / стоп 25 / 168 ч", 0.10, 0.25, 168),
                             ("тейк 20 / стоп 25 / 168 ч", 0.20, 0.25, 168), ("без тейка, стоп 25 / 48 ч", None, 0.25, 48),
                             ("без тейка, стоп 25 / 72 ч", None, 0.25, 72), ("без тейка, стоп 25 / 168 ч", None, 0.25, 168),
                             ("без тейка, стоп 50 / 168 ч", None, 0.50, 168)):
        show(journal(C, tp, sl, hold), nm)

    print("\nУстойчивость: сетка удержания при тейке 10 и 15 / стопе 25; разница с текущим (10 / 25 / 48 ч) — по тем же входам:")
    B = journal(C, 0.10, 0.25, 48).set_index(["s", "T"])
    for tp in (0.10, 0.15):
        for hold in (48, 72, 96, 120, 168, 240):
            R = journal(C, tp, sl=0.25, hold=hold); x = R.net
            d = (R.set_index(["s", "T"]).net - B.net).dropna()
            print(f"  тейк {tp * 100:.0f} / стоп 25 / {hold:3d} ч: n={len(R)}, {x.mean() * 100:+.2f}% на сделку, итог {x.sum() * 10:+.1f} USDT, "
                  f"в плюсе {(x > 0).mean():.0%}, по времени {(R.why == 'время').mean():.0%} | к текущему на тех же {len(d)} входах "
                  f"{d.mean() * 100:+.2f}% (t {d.mean() / d.std() * np.sqrt(len(d)) if d.std() > 0 else 0:+.1f}; лучше {(d > 1e-9).sum()}, "
                  f"хуже {(d < -1e-9).sum()})")
