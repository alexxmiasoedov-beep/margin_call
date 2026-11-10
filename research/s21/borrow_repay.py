"""Отдача против цены как сделки, в равных условиях с контролем. Ячейки из borrow_study.py: монета в канале (сейчас и
4 ч назад), отдача за 24 ч (REP) за 4 ч выросла в 1,5+ раза и на 20+ тыс. $ (займ — нет), цена за 4 ч ±5%+; контроль — те же
монеты и ход цены без ускорения займа и отдачи. Шорт 168 ч (и 72 ч), стоп 25% и 50%, комиссия 0,1%, фактический фандинг,
хедж BTC. Пересечения — по входам ДО нашего: сигнал ↩️ (repay_hold.signals) и журнал «канал» за сутки до входа.
Запуск из папки с данными: python3 s21/borrow_repay.py"""
import os
import sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, HERE)
from borrow_trades import sims, thin
from repay_hold import signals

D = pd.read_pickle("s21/panel.pkl")
RP = signals().groupby("s")["T"].apply(lambda x: np.sort(x.values)).to_dict()
J = pd.read_pickle("s20/trades.pkl"); J = J[J.journal == "канал"]
CH = J.groupby("s").te.apply(lambda x: np.sort(x.values)).to_dict()


def before(idx, R):
    return np.array([bool(np.any(((v := idx.get(s, np.zeros(0))) >= T - 86400) & (v <= T))) for s, T in zip(R.s, R["T"])])


def show(R, name):
    tt = lambda v: v.mean() / v.std() * np.sqrt(len(v))
    x = R.net; cut = R["T"].median(); h = R["T"] < cut
    q = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("Q")).net.mean()
    mo = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("M")).net.sum()
    rp, ch = before(RP, R), before(CH, R); free = ~rp & ~ch
    print(f"  {name}: n={len(R)}, {x.mean() * 100:+.2f}% на сделку (t {tt(x):+.1f}; медиана {x.median() * 100:+.1f}%, в плюсе "
          f"{(x > 0).mean():.0%}, стопов {(R.why == 'стоп').mean():.0%}), хедж BTC {R.hedged.mean() * 100:+.2f}% | половины "
          f"{x[h].mean() * 100:+.2f}/{x[~h].mean() * 100:+.2f}% | месяцев в плюсе {(mo > 0).sum()}/{len(mo)}, кварталов "
          f"{(q > 0).sum()}/{len(q)} | после ↩️ {rp.mean():.0%}, после «канала» {ch.mean():.0%}; без них {x[free].mean() * 100:+.2f}% "
          f"(n={free.sum()}, t {tt(x[free]):+.1f})")
    print("     кварталы: " + ", ".join(f"{k} {v * 100:+.1f}%" for k, v in q.items()))


if __name__ == "__main__":
    up, dn = D.r4 >= 0.05, D.r4 <= -0.05
    acc_b = (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3) & D.in4
    acc_r = (D.rep >= 1.5 * D.rep4) & (D.rep >= 20e3) & D.in4
    cells = (("отдача ускорилась, цена +5%+", acc_r & ~acc_b & up), ("отдача ускорилась, цена −5%−", acc_r & ~acc_b & dn),
             ("отдача ускорилась, ход ±5%+", acc_r & ~acc_b & (up | dn)),
             ("контроль: без ускорения, ход ±5%+", D.in4 & ~acc_b & ~acc_r & (up | dn)))
    for nm, m in cells:
        E = thin(D[m]); print(nm)
        for hn, kw in (("72 ч, стоп 25%", dict(sl=0.25, hold_h=72)), ("168 ч, стоп 25%", dict(sl=0.25, hold_h=168)),
                       ("168 ч, стоп 50%", dict(sl=0.5, hold_h=168))):
            show(sims(E, **kw), hn)
