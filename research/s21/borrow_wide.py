"""Широкий вариант по итогам borrow_control.py: монета в маржинальном канале (сейчас и 4 ч назад) и цена фьючерса за 4 ч
изменилась на 5%+ — с ускорением займа/отдачи или без → шорт. Две заранее заданные проверки: T1 — цена упала на 5%+,
T2 — выросла на 5%+ (у действующего правила канала рост +8…+17% за 4 ч, выход за сутки — для сравнения). Удержание 72 и
168 ч, стоп 25%, комиссия 0,1%, фактический фандинг, хедж BTC; t, половины, кварталы, пересечение с журналом «канал»
(s20/trades.pkl): деление сделок — только по входам «канала» за сутки ДО нашего входа (вход «канала» после нашего —
заглядывание вперёд: это значит, что монета выросла ещё на 8%+, шорт заведомо хуже). Запуск из папки с данными: python3 s21/borrow_wide.py"""
import os
import sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, HERE)
from borrow_trades import sims, thin

D = pd.read_pickle("s21/panel.pkl")
J = pd.read_pickle("s20/trades.pkl"); J = J[J.journal == "канал"]
IDX = J.groupby("s").te.apply(lambda x: np.sort(x.values)).to_dict()


def show(R, name):
    x = R.net; cut = R["T"].median(); h = R["T"] < cut
    q = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("Q")).net.mean()
    near = lambda a, b: np.array([bool(np.any(((v := IDX.get(s, np.zeros(0))) - T >= a) & (v - T <= b)))
                                  for s, T in zip(R.s, R["T"])])
    ov, after = near(-86400, 0), near(1, 86400)
    tt = lambda v: v.mean() / v.std() * np.sqrt(len(v))
    print(f"  {name}: n={len(R)} ({len(R) / 20:.0f} в месяц), {x.mean() * 100:+.2f}% на сделку (t {tt(x):+.1f}; медиана "
          f"{x.median() * 100:+.1f}%, в плюсе {(x > 0).mean():.0%}, стопов {(R.why == 'стоп').mean():.0%}), с хеджем BTC "
          f"{R.hedged.mean() * 100:+.2f}% (t {tt(R.hedged.dropna()):+.1f}) | половины {x[h].mean() * 100:+.2f}/{x[~h].mean() * 100:+.2f}% | "
          f"кварталов в плюсе {(q > 0).sum()}/{len(q)} | вход «канала» за сутки до {ov.mean():.0%} (их сделки "
          f"{x[ov].mean() * 100:+.2f}%), без них {x[~ov].mean() * 100:+.2f}% (n={(~ov).sum()}, t {tt(x[~ov]):+.1f}) | "
          f"вход «канала» в следующие сутки {after.mean():.0%} (их сделки {x[after].mean() * 100:+.2f}% — для справки, это будущее)")
    print("     кварталы: " + ", ".join(f"{k} {v * 100:+.1f}%" for k, v in q.items()))


if __name__ == "__main__":
    for nm, m in (("T1 цена за 4 ч −5%−", D.in4 & (D.r4 <= -0.05)), ("T2 цена за 4 ч +5%+", D.in4 & (D.r4 >= 0.05))):
        E = thin(D[m])
        print(nm)
        for hn, hold in (("72 ч", 72), ("168 ч", 168)):
            show(sims(E, sl=0.25, hold_h=hold), f"{hn}, стоп 25%")
