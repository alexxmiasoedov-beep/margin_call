"""Корейская премия как сигнал (часовая панель kr_panel.py): цена монеты на Upbit/Bithumb в долларах по курсу USDT/KRW
той же биржи против фьючерса Binance. Общая «кимчи-премия» уходит в курс USDT/KRW, остаётся перекос самой монеты.
Скачок — премия выше своей медианы за 7 суток на X п. п. Корейская розница переплачивает — разрыв закрывается падением?

A. событие: скачок премии ≥ 3/5/10 п. п., корейский оборот за час ≥ 50 тыс. $ (иначе цена устаревшая), одно событие на
   монету за 72 ч → шорт 24/72/168 ч, стоп 25%; зеркально — провал премии → лонг;
B. каждый день в 04:00 UTC (13:00 Сеул): шорт 5 монет с самым большим скачком, лонг 5 с самым глубоким провалом, 1 и 3 суток.
Комиссия 0,1%, фактический фандинг. Запуск из папки с данными (после kr_panel.py): python3 s15/kr_premium.py"""
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import trade

P = pickle.load(open("s15/kr_panel.pkl", "rb"))


def prep():
    out = []
    for s, d in P.items():
        d = d.copy()
        liq = d.kr >= 5e4
        d["prem_l"] = d.prem.where(liq)
        d["dev"] = d.prem_l - d.prem_l.shift(1).rolling(168, min_periods=48).median()
        d["s"] = s
        out.append(d[["s", "T", "j", "kr", "share", "prem_l", "dev", "r4", "r24"]])
    return pd.concat(out, ignore_index=True)


def events(D, thr, side, gap_h=72):
    m = D.dev >= thr if side < 0 else D.dev <= -thr
    ev, last = [], {}
    for r in D[m].sort_values("T").itertuples():
        if r.T - last.get(r.s, -1e18) >= gap_h * 3600:
            ev.append(r); last[r.s] = r.T
    return pd.DataFrame(ev)


def run(E, side, **kw):
    rows = [dict(e._asdict(), **x) for e in E.itertuples() if (x := trade(e.s, e.j, side=side, **kw))]
    return pd.DataFrame(rows)


def line(r, cut):
    if not len(r):
        return "нет сделок"
    h = r["T"] < cut
    return (f"n={len(r):4d} | {r.net.mean() * 100:+5.2f}% (в плюсе {(r.net > 0).mean():3.0%}, фандинг {r.fund.mean() * 100:+4.1f}%) | "
            f"1-я/2-я половина {r.net[h].mean() * 100:+5.2f}/{r.net[~h].mean() * 100:+5.2f}%")


if __name__ == "__main__":
    D = prep()
    cut = float(D["T"].median())
    q = D.dev.dropna()
    print(f"строк с ликвидной ценой: {D.prem_l.notna().sum():,}; премия монеты: медиана {D.prem_l.median() * 100:+.2f}%, "
          f"скачок: 1-й/99-й перцентиль {q.quantile(0.01) * 100:+.1f}/{q.quantile(0.99) * 100:+.1f} п. п., 99,9-й {q.quantile(0.999) * 100:+.1f}")
    for side, nm in ((-1, "шорт после скачка премии"), (1, "лонг после провала премии")):
        print(f"\nA. {nm}:")
        for thr in (0.03, 0.05, 0.10):
            E = events(D, thr, side)
            if len(E) < 20:
                print(f"  порог {thr * 100:.0f} п. п.: событий {len(E)}"); continue
            for hold in (24, 72, 168):
                print(f"  порог {thr * 100:.0f} п. п., {hold:3d} ч, стоп 25%: {line(run(E, side, sl=0.25, hold_h=hold), cut)}")
    print("\nB. корзина каждый день в 04:00 UTC (шорт 5 с наибольшим скачком, лонг 5 с наименьшим):")
    X = D[((D["T"] // 3600) % 24 == 4) & D.dev.notna()]
    for hold in (24, 72):
        rows = []
        for T, g in X.groupby("T"):
            if len(g) < 30:
                continue
            g = g.sort_values("dev")
            sh = [trade(r.s, r.j, sl=None, hold_h=hold, side=-1) for r in g.tail(5).itertuples()]
            lo = [trade(r.s, r.j, sl=None, hold_h=hold, side=1) for r in g.head(5).itertuples()]
            sh = [x["net"] for x in sh if x]; lo = [x["net"] for x in lo if x]
            if sh and lo:
                rows.append(dict(T=T, short=np.mean(sh), long=np.mean(lo)))
        R = pd.DataFrame(rows)
        h = R["T"] < cut
        R["pair"] = (R.short + R.long) / 2
        print(f"  {hold} ч, дней {len(R)}: шорт-нога {R.short.mean() * 100:+.2f}%, лонг-нога {R.long.mean() * 100:+.2f}%, "
              f"пара {R.pair.mean() * 100:+.2f}% (1-я/2-я {R.pair[h].mean() * 100:+.2f}/{R.pair[~h].mean() * 100:+.2f}%)")
