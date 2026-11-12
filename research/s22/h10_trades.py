"""Г10 (а), сделки: шорт перпа при открытии займа монеты в марже Binance (первая запись ставки займа в публичной истории,
s22/h10_a.pkl из h10_margin.py). Сроки 7/14/21/30 суток, стоп +50% и +100% при плече ×1, комиссия, фактический фандинг,
хедж BTC; половины, по кварталам. Сравнение с журналом 🆕 (s12/final_journals.pkl «A», шорт 21 сутки, стоп +60%) на
общих монетах: тот же шорт, открытый при открытии займа. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import CUT, DAY, ct, summ
from borrow_trades import sims

if __name__ == "__main__":
    EA = pd.read_pickle("s22/h10_a.pkl").sort_values("T").reset_index(drop=True)
    for hold in (7, 14, 21, 30):
        for sl in (0.5, 1.0):
            R = sims(EA, sl=sl, hold_h=hold * 24)
            q = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("Q")).net.mean()
            print(f"{hold:2d} сут, стоп +{sl * 100:.0f}%: {summ(R.net.values, R['T'].values)}; стопов {(R.why == 'стоп').mean():.0%}; "
                  f"с хеджем BTC {np.nanmean(R.hedged) * 100:+.2f}%; итог {R.net.sum() * 100:+.0f}% по {len(R)} сделкам; "
                  f"кварталов в плюсе {(q > 0).sum()}/{len(q)}")
    NT = pd.read_pickle("s12/final_journals.pkl")["A"]
    m = []
    for e in EA.itertuples():
        g = NT[(NT.s == e.s) & (NT.te > e.T) & (NT.te <= e.T + 15 * DAY)]
        if len(g):
            m.append(dict(s=e.s, T=e.T, nt_te=g.te.iloc[0], nt_sp=g.sp.iloc[0]))
    M = pd.DataFrame(m)
    R = sims(M, sl=0.6, hold_h=21 * 24).merge(M, on=["s", "T"])
    print(f"\nОбщие с 🆕 монеты: {len(R)}; 🆕 входил через {((R.nt_te - R['T']) / DAY).median():.1f} сут после открытия займа (медиана)")
    print(f"  шорт с открытия займа, 21 сут, стоп +60%: {R.net.mean() * 100:+.2f}% (медиана {R.net.median() * 100:+.2f}%); "
          f"сделки 🆕 по тем же монетам: {R.nt_sp.mean() * 100:+.2f}% (медиана {R.nt_sp.median() * 100:+.2f}%)")
