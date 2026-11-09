"""«Корейский набег» — контроль: даёт ли плюс сама доля Кореи или любой рост на 10% за 4 ч.
Сравнение (выход 🇹🇷: тейк 10 / стоп 15 / 24 ч; одна сделка на монету за 48 ч; оборот за час ≥ 200 тыс. $):
- рост ≥ 10% за 4 ч у монет, которые торгуются в Корее, при разной доле Кореи и её скачке;
- то же у фьючерсов, которых нет на Upbit/Bithumb (по 15-мин свечам Binance на закрытии часа).
Плюс выбранное правило по кварталам и с другими выходами. Запуск из папки с данными: python3 s15/kr_raid2.py"""
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import K, trade
from kr_raid import P, kr_signals, overlap, with_trades, line

EX = dict(tp=0.10, sl=0.15, hold_h=24)


def select(cond, gap_h=48):
    ev = []
    for s, d in P.items():
        m = (cond(d) & (d.kr + d.bin >= 2e5)).values
        last = -1e18
        for r in d[m].itertuples():
            if r.T - last >= gap_h * 3600:
                ev.append(dict(s=s, j=int(r.j), T=int(r.T), share=r.share, norm=r.norm, r4=r.r4)); last = r.T
    return pd.DataFrame(ev)


def not_korean(rise=0.10, gap_h=48):
    """Фьючерсы без рынка к воне: рост ≥ rise за 4 ч на закрытии часа, оборот фьючерса за час ≥ 200 тыс. $."""
    ev = []
    for s, a in K.items():
        if s in P:
            continue
        t, c, q = a["t"], a["c"].astype(float), a["qv"].astype(float)
        j = np.flatnonzero((t + 900) % 3600 == 0); j = j[j >= 16]
        cs = np.r_[0.0, np.cumsum(q)]
        ok = (c[j] / c[j - 16] - 1 >= rise) & (cs[j + 1] - cs[j - 3] >= 2e5) & (q[j] > 0) & (q[j - 16] > 0)
        last = -1e18
        for jj in j[ok]:
            T = int(t[jj]) + 900
            if T - last >= gap_h * 3600:
                ev.append(dict(s=s, j=int(jj), T=T)); last = T
    return pd.DataFrame(ev)


if __name__ == "__main__":
    cut = float(np.median(np.concatenate([d["T"].values for d in P.values()])))
    S20 = kr_signals(); S20 = S20[S20.share >= 0.20]
    print("рост ≥ 10% за 4 ч, выход 🇹🇷 10/15/24 ч, без сигналов 🇰🇷 за 24 ч до:")
    groups = {
        "монета в Корее, доля Кореи < 5%": lambda d: (d.r4 >= 0.10) & (d.share < 0.05),
        "доля 5–10%": lambda d: (d.r4 >= 0.10) & (d.share >= 0.05) & (d.share < 0.10),
        "доля 10–20%": lambda d: (d.r4 >= 0.10) & (d.share >= 0.10) & (d.share < 0.20),
        "доля ≥ 20%, без скачка (< ×1,5 обычной)": lambda d: (d.r4 >= 0.10) & (d.share >= 0.20) & (d.share < 1.5 * d.norm),
        "доля ≥ 20% и ×3 (набег)": lambda d: (d.r4 >= 0.10) & (d.share >= 0.20) & (d.share >= 3 * d.norm),
        "доля ≥ 30% и ×3 (набег)": lambda d: (d.r4 >= 0.10) & (d.share >= 0.30) & (d.share >= 3 * d.norm),
    }
    for nm, f in groups.items():
        E = select(f)
        E = E[~overlap(E, S20)] if len(E) else E
        print(f"  {nm:42s} {line(with_trades(E, **EX), cut)}")
    NK = not_korean()
    print(f"  {'фьючерса нет на Upbit/Bithumb':42s} {line(with_trades(NK, **EX), cut)}")

    print("\nнабег: доля ≥ 20% и ×3, рост ≥ 10% — другие выходы и кварталы:")
    E = select(groups["доля ≥ 20% и ×3 (набег)"]); E = E[~overlap(E, S20)]
    for nm, kw in (("🇹🇷 10/15/24 ч", EX), ("🇰🇷 10/25/48 ч", dict(tp=0.10, sl=0.25, hold_h=48)),
                   ("без тейка, стоп 25%, 48 ч", dict(tp=None, sl=0.25, hold_h=48)), ("без тейка, стоп 50%, 168 ч", dict(tp=None, sl=0.50, hold_h=168))):
        print(f"  {nm:28s} {line(with_trades(E, **kw), cut)}")
    r = with_trades(E, **EX)
    q = r.groupby(pd.to_datetime(r["T"], unit="s").dt.to_period("Q")).net.agg(["size", "mean"])
    print("  по кварталам (🇹🇷 выход): " + ", ".join(f"{k} {v['mean'] * 100:+.1f}% ({int(v['size'])})" for k, v in q.iterrows()))
    m = r.groupby(pd.to_datetime(r["T"], unit="s").dt.to_period("M")).net.sum()
    print(f"  месяцев в плюсе {(m > 0).sum()}/{len(m)}; итог при марже 1 USDT ×10: {r.net.sum() * 10:+.1f} USDT")
