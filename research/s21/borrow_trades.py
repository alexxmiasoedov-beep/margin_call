"""Сделки по находкам borrow_study.py: монета в маржинальном канале, займ за 24 ч (BOR) за 4 ч вырос в 1,5+ раза
(и ≥ 50 тыс. $), а цена за 4 ч упала на 5%+ («шорты выигрывают и добавляют») → шорт на закрытии часа. Для сравнения —
те же ячейки, что пересекаются с действующими правилами: займ растёт на росте (сигнал канала, s9 CHNG) и отдача на
росте/падении (↩️). Одна сделка на монету за 24 ч. Комиссия 0,1%, фактический фандинг, стоп по максимуму 15-мин свечи.
Хедж — лонг BTC на ту же сумму (как у 🏦). Проверки: половины, кварталы, без 3 дней с наибольшим числом сигналов,
пороги. Нужен s21/panel.pkl (borrow_study.py). Запуск из папки с данными: python3 s21/borrow_trades.py"""
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import BAR, FEE, K, funding, trade

D = pd.read_pickle("s21/panel.pkl")
BT = K["BTC"]["t"].astype(np.int64)


def btc_leg(t0, t1):
    i0, i1 = np.searchsorted(BT, t0 - BAR), np.searchsorted(BT, t1 - BAR)
    if i1 >= len(BT) or BT[i0] != t0 - BAR or BT[i1] != t1 - BAR:
        return np.nan
    fr = funding("BTC"); f = float(fr[(fr[:, 0] > t0) & (fr[:, 0] <= t1), 1].sum())
    c = K["BTC"]["c"]
    return float(c[i1]) / float(c[i0]) - 1 - FEE - f


def thin(d, gap=86400):
    keep, last = [], {}
    for i, (s, T) in enumerate(zip(d.s.values, d["T"].values)):
        if T - last.get(s, -1e18) >= gap:
            keep.append(i); last[s] = T
    return d.iloc[keep]


def sims(E, sl=0.5, hold_h=168):
    rows = []
    for e in E.itertuples():
        t = K[e.s]["t"]; j = int(np.searchsorted(t, e.T - BAR))
        if j >= len(t) or t[j] != e.T - BAR:
            continue
        r = trade(e.s, j, sl=sl, hold_h=hold_h)
        if r is None:
            continue
        t1 = float(t[j + r["bars"]]) + BAR
        rows.append(dict(r, s=e.s, T=e.T, hedged=r["net"] + btc_leg(float(e.T), t1)))
    return pd.DataFrame(rows)


def report(R, name):
    if len(R) < 20:
        print(f"  {name}: мало сделок ({len(R)})"); return
    cut = R["T"].median(); h = R["T"] < cut
    day = pd.to_datetime(R["T"], unit="s").dt.date
    top = day.value_counts().head(3).index
    ex = R[~day.isin(top)]
    q = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("Q")).net.mean()
    m = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("M")).net.sum()
    print(f"  {name}: n={len(R)} ({len(R) / 20:.0f} в месяц), {R.net.mean() * 100:+.2f}% на сделку (медиана {R.net.median() * 100:+.1f}%, "
          f"в плюсе {(R.net > 0).mean():.0%}, стопов {(R.why == 'стоп').mean():.0%}), с хеджем BTC {R.hedged.mean() * 100:+.2f}% | "
          f"половины {R.net[h].mean() * 100:+.2f}/{R.net[~h].mean() * 100:+.2f}% | без 3 самых частых дней {ex.net.mean() * 100:+.2f}% "
          f"({', '.join(str(x) for x in top)}) | месяцев в плюсе {(m > 0).sum()}/{len(m)}")
    print("     кварталы: " + ", ".join(f"{k} {v * 100:+.1f}%" for k, v in q.items()))


if __name__ == "__main__":
    up, dn = D.r4 >= 0.05, D.r4 <= -0.05
    acc_b = (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3) & D.in4
    acc_r = (D.rep >= 1.5 * D.rep4) & (D.rep >= 20e3) & D.in4
    A = thin(D[acc_b & ~acc_r & dn])
    print("A. займ ускорился, цена за 4 ч −5%− (новое):")
    for nm, kw in (("72 ч, стоп 25%", dict(sl=0.25, hold_h=72)), ("168 ч, стоп 25%", dict(sl=0.25, hold_h=168)),
                   ("168 ч, стоп 50%", dict(sl=0.5, hold_h=168))):
        report(sims(A, **kw), nm)
    print("\n   пороги (168 ч, стоп 50%):")
    for nm, m in (("займ ×2, цена −5%", (D.bor >= 2 * D.bor4) & (D.bor >= 50e3) & D.in4 & ~acc_r & dn),
                  ("займ ×1,5, цена −10%", acc_b & ~acc_r & (D.r4 <= -0.10)),
                  ("займ ×1,5, цена −3%", acc_b & ~acc_r & (D.r4 <= -0.03)),
                  ("займ ×1,5 ≥ 200 тыс. $, цена −5%", (D.bor >= 1.5 * D.bor4) & (D.bor >= 200e3) & D.in4 & ~acc_r & dn)):
        report(sims(thin(D[m]), sl=0.5, hold_h=168), nm)
    print("\nДля сравнения — ячейки, близкие к действующим правилам (168 ч, стоп 50%):")
    report(sims(thin(D[acc_b & ~acc_r & up]), sl=0.5, hold_h=168), "займ ускорился, цена +5%+ (≈ сигнал канала / CHNG)")
    report(sims(thin(D[acc_r & ~acc_b & up]), sl=0.5, hold_h=168), "отдача ускорилась, цена +5%+ (≈ ↩️)")
    report(sims(thin(D[acc_r & ~acc_b & dn]), sl=0.5, hold_h=168), "отдача ускорилась, цена −5%− (≈ ↩️)")
    A.to_pickle("s21/cell_A.pkl")
