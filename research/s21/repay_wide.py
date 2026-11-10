"""Широкое правило отдачи как журнал бота. Монета в маржинальном канале (пост не старше 30 мин сейчас и 4 ч назад), на закрытии
часа: отдача за 24 ч (REP) выросла к значению 4 ч назад в X раз и не меньше R тыс. $, займ (BOR) при этом не вырос в 1,5 раза
(иначе это набор позиций, а не выход), цена фьючерса за 4 ч изменилась на M% в любую сторону → шорт без тейка, стоп, выход по
времени. Как у бота: по монете одна открытая сделка, новая — не раньше чем через 24 ч после прежнего входа. Основной вариант
задан заранее по borrow_study.py: X = 1,5, R = 20 тыс. $, M = 5%; остальные — проверка устойчивости. Сделки —
s15/common.trade (стоп с проскальзыванием 0,2%, комиссия 0,1%, фактический фандинг), хедж BTC — как у 🏦.
Нужны s21/panel.pkl (borrow_study.py) и s20/trades.pkl. Запуск из папки с данными: python3 s21/repay_wide.py"""
import os
import sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, HERE)
from common import BAR, K, trade
from borrow_trades import btc_leg
from repay_hold import CUT, signals

D = pd.read_pickle("s21/panel.pkl").sort_values("T").reset_index(drop=True)
RP = signals().groupby("s")["T"].apply(lambda x: np.sort(x.values)).to_dict()
J = pd.read_pickle("s20/trades.pkl"); J = J[J.journal == "канал"]
CH = J.groupby("s").te.apply(lambda x: np.sort(x.values)).to_dict()


def mask(x=1.5, rmin=20e3, mv=0.05, no_bor=True):
    m = D.in4 & (D.rep >= x * D.rep4) & (D.rep >= rmin) & (D.r4.abs() >= mv)
    if no_bor:
        m &= ~((D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3))
    return m


def journal(m, sl=0.5, hold=168):
    out, last = [], {}
    for r in D[m].itertuples():
        lo, lc = last.get(r.s, (-1e18, -1e18))
        if r.T - lo < 86400 or r.T < lc:
            continue
        t = K[r.s]["t"]; j = int(np.searchsorted(t, r.T - BAR))
        if j >= len(t) or t[j] != r.T - BAR:
            continue
        x = trade(r.s, j, sl=sl, hold_h=hold)
        if x is None:
            continue
        t1 = float(t[j + x["bars"]]) + BAR
        last[r.s] = (r.T, t1)
        out.append(dict(s=r.s, T=r.T, t1=t1, r4=r.r4, net=x["net"], why=x["why"], hedged=x["net"] + btc_leg(float(r.T), t1)))
    return pd.DataFrame(out)


def before(idx, R):
    return np.array([bool(np.any(((v := idx.get(s, np.zeros(0))) >= T - 86400) & (v <= T))) for s, T in zip(R.s, R["T"])])


def show(R, name, full=True):
    x = R.net; tt = x.mean() / x.std() * np.sqrt(len(x))
    if not full:
        print(f"  {name:34s} n={len(R):4d}, {x.mean() * 100:+.2f}% (t {tt:+.1f}), в плюсе {(x > 0).mean():.0%}, половины "
              f"{x[R['T'] < CUT].mean() * 100:+.2f}/{x[R['T'] >= CUT].mean() * 100:+.2f}%")
        return
    h1, h2 = x[R["T"] < CUT], x[R["T"] >= CUT]
    eq = (x * 10).cumsum(); dd = (eq - eq.cummax()).min()
    mo = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("M")).net.sum()
    q = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("Q")).net.mean()
    ev = sorted([(a, 1) for a in R["T"]] + [(b, -1) for b in R.t1]); cur = mx = 0
    for _, d in ev:
        cur += d; mx = max(mx, cur)
    day = pd.to_datetime(R["T"], unit="s").dt.date; top = day.value_counts().head(3).index
    free = ~before(RP, R) & ~before(CH, R)
    print(f"  {name}: n={len(R)} ({len(R) / 20:.0f} в месяц), в плюсе {(x > 0).mean():.0%}, {x.mean() * 100:+.2f}% на сделку "
          f"(t {tt:+.1f}; медиана {x.median() * 100:+.1f}%), итог {x.sum() * 10:+.1f} USDT (1 × 10), просадка {dd:.1f}, стопов "
          f"{(R.why == 'стоп').mean():.0%}, хедж BTC {R.hedged.mean() * 100:+.2f}% | половины {h1.mean() * 100:+.2f}% ({len(h1)}) / "
          f"{h2.mean() * 100:+.2f}% ({len(h2)}) | после роста {x[R.r4 > 0].mean() * 100:+.2f}% ({(R.r4 > 0).sum()}), после падения "
          f"{x[R.r4 < 0].mean() * 100:+.2f}% ({(R.r4 < 0).sum()}) | месяцев в плюсе {(mo > 0).sum()}/{len(mo)}, кварталов "
          f"{(q > 0).sum()}/{len(q)} | одновременно до {mx} | без 3 самых частых дней {x[~day.isin(top)].mean() * 100:+.2f}% | "
          f"без входов после ↩️ и «канала» {x[free].mean() * 100:+.2f}% (n={free.sum()})")
    print("     кварталы: " + ", ".join(f"{k} {v * 100:+.1f}%" for k, v in q.items()))


if __name__ == "__main__":
    print("Основной вариант (×1,5, от 20 тыс. $, ход ±5%):")
    for nm, kw in (("168 ч, стоп 50%", dict(sl=0.5, hold=168)), ("168 ч, стоп 25%", dict(sl=0.25, hold=168))):
        show(journal(mask(), **kw), nm)
    print("\nСрок (стоп 50%):")
    for hold in (48, 72, 120, 168, 240):
        show(journal(mask(), sl=0.5, hold=hold), f"{hold} ч", full=False)
    print("\nПороги (168 ч, стоп 50%):")
    for x in (1.5, 2.0):
        for rmin in (20e3, 100e3):
            for mv in (0.03, 0.05, 0.10):
                show(journal(mask(x, rmin, mv), sl=0.5, hold=168), f"×{x:g}, от {rmin / 1e3:.0f} тыс. $, ход {mv * 100:.0f}%", full=False)
    show(journal(mask(no_bor=False), sl=0.5, hold=168), "без условия «займ не вырос»", full=False)
