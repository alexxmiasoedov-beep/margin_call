"""Шорт после корейского листинга как журнал: правило без заглядывания вперёд и его итоги.

Каждый листинг к воне на Upbit или Bithumb — отдельный сигнал (без склейки). «Второй листинг» — монета в момент открытия
торгов уже торгуется к воне на другой корейской бирже (старый рынок или открыт раньше). Сигнал пропускается, если по монете
уже открыта сделка. Шорт в закрытии 15-мин свечи открытия торгов; фьючерсу Binance не меньше суток (и 7 суток).
Итоги по кварталам, с хеджем лонгом BTC на ту же сумму (как у 🏦), просадка и число одновременных сделок.

Запуск из папки с данными: python3 s15/kr_short3.py"""
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BAR, FEE, K, fut_of, funding, live, trade
from kr_short import L, MK, NEW

BT = K["BTC"]["t"]


def signals():
    seen = {}
    for x in L:
        seen.setdefault(x["base"], {})[x["ex"]] = x["t"]
    out = []
    for x in sorted(L, key=lambda x: x["t"]):
        other = "bithumb" if x["ex"] == "upbit" else "upbit"
        old = x["base"] in MK[other] and (other, x["base"]) not in NEW
        earlier = seen[x["base"]].get(other, np.inf) < x["t"]
        out.append(dict(x, second=bool(old or earlier)))
    return out


def btc_leg(t0, t1):
    """Лонг BTC с t0 по t1 (закрытия 15-мин свечей): цена − комиссия − фандинг."""
    i0, i1 = np.searchsorted(BT, t0 - BAR), np.searchsorted(BT, t1 - BAR)
    if i1 >= len(BT) or BT[i0] != t0 - BAR or BT[i1] != t1 - BAR:
        return np.nan
    c = K["BTC"]["c"]; fr = funding("BTC")
    f = float(fr[(fr[:, 0] > t0) & (fr[:, 0] <= t1), 1].sum())
    return float(c[i1]) / float(c[i0]) - 1 - FEE - f


def journal(S, hold_h=168, sl=0.5, tp=None, min_age_d=1, only_second=False):
    rows, busy = [], {}
    for e in S:
        if only_second and not e["second"]:
            continue
        s, _ = fut_of(e["base"])
        if s is None or busy.get(s, -1) > e["t"]:
            continue
        a = K[s]; t = a["t"]
        if live(s)[0] > e["t"] - min_age_d * 86400:
            continue
        j = int(np.searchsorted(t, e["t"], side="right")) - 1
        if j < 8 or t[j] < e["t"] - BAR:
            continue
        r = trade(s, j, tp=tp, sl=sl, hold_h=hold_h)
        if r is None:
            continue
        t0 = float(t[j]) + BAR; t1 = float(t[j + r["bars"]]) + BAR
        busy[s] = t1
        rows.append(dict(r, t=e["t"], t0=t0, t1=t1, sym=s, ex=e["ex"], second=e["second"], hedged=r["net"] + btc_leg(t0, t1)))
    return pd.DataFrame(rows)


def report(r, name):
    h = r.t < r.t.median()
    eq = r.sort_values("t1").net.cumsum().values
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
    conc = max(((r.t0 <= x) & (r.t1 > x)).sum() for x in r.t0)
    months = pd.to_datetime(r.t, unit="s").dt.to_period("M")
    mm = r.groupby(months).net.sum()
    q = r.groupby(pd.to_datetime(r.t, unit="s").dt.to_period("Q")).net.agg(["size", "mean"])
    print(f"\n{name}: сделок {len(r)} ({len(r) / ((r.t.max() - r.t.min()) / 86400 / 30.4):.1f} в месяц), на сделку {r.net.mean() * 100:+.2f}% "
          f"(медиана {r.net.median() * 100:+.1f}%, в плюсе {(r.net > 0).mean():.0%}, стопов {(r.why == 'стоп').mean():.0%}), "
          f"с хеджем BTC {r.hedged.mean() * 100:+.2f}%; 1-я/2-я половина {r.net[h].mean() * 100:+.2f}/{r.net[~h].mean() * 100:+.2f}%")
    print(f"  итог при марже 1 USDT ×1: {r.net.sum():+.2f} USDT, худшая просадка {dd:+.2f} USDT, месяцев в плюсе {(mm > 0).sum()}/{len(mm)}, "
          f"одновременно до {conc} сделок; худшая сделка {r.net.min() * 100:+.1f}%, лучшая {r.net.max() * 100:+.1f}%")
    print("  по кварталам: " + ", ".join(f"{k} {v['mean'] * 100:+.1f}% ({int(v['size'])})" for k, v in q.iterrows()))


if __name__ == "__main__":
    S = signals()
    print(f"листингов {len(S)}, из них «второй» (монета уже торгуется к воне на другой корейской бирже) {sum(e['second'] for e in S)}")
    for nm, kw in (("все листинги, 168 ч, стоп 50%", dict()),
                   ("все листинги, 168 ч, стоп 25%", dict(sl=0.25)),
                   ("все листинги, 72 ч, стоп 25%", dict(hold_h=72, sl=0.25)),
                   ("все листинги, фьючерс старше 7 дней, 168 ч, стоп 50%", dict(min_age_d=7)),
                   ("только «второй» листинг, 168 ч, стоп 50%", dict(only_second=True)),
                   ("только «второй» листинг, 72 ч, стоп 25%", dict(only_second=True, hold_h=72, sl=0.25))):
        r = journal(S, **kw)
        report(r, nm)
        if nm.startswith("все листинги, 168 ч, стоп 50%"):
            for g, m in (("Upbit", r.ex == "upbit"), ("Bithumb", r.ex == "bithumb"), ("второй", r.second), ("первый", ~r.second)):
                x = r[m]; hh = x.t < r.t.median()
                print(f"    {g:8s} n={len(x):3d}: {x.net.mean() * 100:+.2f}% (в плюсе {(x.net > 0).mean():.0%}), с хеджем {x.hedged.mean() * 100:+.2f}%, "
                      f"1-я/2-я половина {x.net[hh].mean() * 100:+.2f}/{x.net[~hh].mean() * 100:+.2f}%")
            r.to_pickle("s15/kr_journal.pkl")
