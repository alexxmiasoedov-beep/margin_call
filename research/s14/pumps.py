"""Пампы монеты день за днём: что было до, во время и после. Памп — цена за 3 дня выросла на 40%+ от минимума этих дней
(между пампами не меньше 30 дней). По каждому дню: цена, сделки, оборот, средний размер сделки, «парные» сделки (по всей
ленте: покупка и продажа одного и того же размера в пределах 2 с — самоторговля), открытый интерес, фандинг, толщина
стакана ±2%. Видно, идут ли отпечатки до роста (их можно ловить заранее) или вместе с ним.

Запуск из папки с данными (после build.py): python3 s14/pumps.py GPS ONE"""
import glob
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import csv_in

RISE, GAP_D, BEFORE, AFTER = 0.40, 30, 14, 10


def events(B):
    d = B.c.groupby(pd.to_datetime(B.index * 60, unit="s").floor("D")).last()
    lo = d.rolling(3, min_periods=1).min().shift(1)
    hit = d[(d / lo - 1) >= RISE]
    ev, last = [], None
    for day in hit.index:
        if last is None or (day - last).days >= GAP_D:
            ev.append(day); last = day
    return ev


def paired(coin, d0, d1):
    """Доля парных сделок по дням: покупка и продажа одного размера в пределах 2 с (по всей ленте)."""
    out = []
    for m in pd.period_range(d0, d1, freq="M"):
        f = glob.glob(f"s14raw/{coin}/aggTrades/{coin}USDT-aggTrades-{m}.zip")
        if not f:
            continue
        d = csv_in(f[0], usecols=[2, 5, 6], names=["id", "p", "q", "f", "l", "t", "m"],
                   dtype={"q": "float64", "t": "int64", "m": "str"})
        d = d[(d.t >= d0.value // 10 ** 6) & (d.t < (d1 + pd.Timedelta(days=1)).value // 10 ** 6)]
        d["sell"] = d.m.str.lower().eq("true")
        b = d[~d.sell].sort_values("t"); s = d[d.sell].sort_values("t")[["t", "q"]].rename(columns={"t": "ts"})
        s["t"] = s.ts
        mt = pd.merge_asof(b[["t", "q"]], s, on="t", by="q", direction="nearest", tolerance=2000)
        b = b.assign(pair=mt.ts.notna().values)
        day = lambda x: pd.to_datetime(x.t, unit="ms").dt.floor("D")
        out.append(pd.DataFrame({"n": d.groupby(day(d)).size(), "pairs": b.groupby(day(b)).pair.sum() * 2}))
    if not out:
        return pd.DataFrame()
    r = pd.concat(out).groupby(level=0).sum()
    return r.assign(share=r.pairs / r.n)


def table(coin):
    X = pickle.load(open(f"s14/{coin}.pkl", "rb")); B = X["bars"]
    day = pd.to_datetime(B.index * 60, unit="s").floor("D"); g = B.groupby(day)
    M = X["metrics"]; oi = M.oi_usd.groupby(pd.to_datetime(M.index, unit="s").floor("D")).last()
    F = X["funding"]; fr = (F.rate / F.iv * 8).groupby(pd.to_datetime(F.index, unit="s").floor("D")).mean()
    D = X["depth"]; dep = (D["d-2"] + D["d+2"]).groupby(pd.to_datetime(D.index, unit="s").floor("D")).mean()
    vol = g.buy_v.sum() + g.sell_v.sum()
    T = pd.DataFrame({"close": g.c.last(), "ret": g.c.last() / g.o.first() - 1, "n": g.n.sum(), "vol": vol,
                      "avg": vol / g.n.sum(), "oi": oi, "fund": fr, "dep2": dep})
    return B, T


def report(coin):
    B, T = table(coin)
    ev = events(B)
    print(f"\n===== {coin}: пампов (+{RISE:.0%} за 3 дня, между ними ≥ {GAP_D} дней): {len(ev)} — "
          + ", ".join(f"{e:%d.%m.%Y}" for e in ev))
    rows = []
    for e in ev:
        P = paired(coin, e - pd.Timedelta(days=40), e + pd.Timedelta(days=AFTER))
        w = T.loc[e - pd.Timedelta(days=40):e + pd.Timedelta(days=AFTER)].join(P[["share"]] if len(P) else None)
        base = w.loc[:e - pd.Timedelta(days=BEFORE + 1)]          # фон: за 40…15 дней до
        pre = w.loc[e - pd.Timedelta(days=7):e - pd.Timedelta(days=1)]   # неделя перед пампом
        on = w.loc[e:e + pd.Timedelta(days=3)]
        top = w.loc[e:e + pd.Timedelta(days=AFTER)].close.idxmax()
        rows.append(dict(event=e, top=top, rise=w.loc[e:].close.max() / w.loc[:e - pd.Timedelta(days=1)].close.iloc[-1] - 1,
                         after=w.close.iloc[-1] / w.loc[e:].close.max() - 1,
                         pre_n=pre.n.mean() / base.n.mean(), pre_vol=pre.vol.mean() / base.vol.mean(),
                         pre_avg=pre.avg.mean() / base.avg.mean(), pre_dep=pre.dep2.mean() / base.dep2.mean(),
                         pre_oi=pre.oi.iloc[-1] / base.oi.mean() if pre.oi.notna().any() else np.nan,
                         pre_pair=pre.share.mean() if "share" in pre else np.nan,
                         base_pair=base.share.mean() if "share" in base else np.nan,
                         on_pair=on.share.mean() if "share" in on else np.nan, fund_on=on.fund.mean()))
        print(f"\n  памп {e:%d.%m.%Y}: рост до вершины {rows[-1]['rise']:+.0%} ({top:%d.%m}), к {AFTER}-му дню от вершины "
              f"{rows[-1]['after']:+.0%}")
        show = w.loc[e - pd.Timedelta(days=BEFORE):e + pd.Timedelta(days=AFTER)]
        print("    день | цена | за день | сделок, тыс. | оборот, млн $ | средняя сделка, $ | парных, % | ОИ, млн $ | фандинг/8 ч | стакан ±2%, тыс. $")
        for dd, r in show.iterrows():
            print(f"    {(dd - e).days:+3d} {dd:%d.%m} | {r.close:.6g} | {r.ret * 100:+6.1f}% | {r.n / 1e3:7.0f} | {r.vol / 1e6:7.1f} | "
                  f"{r.avg:6.0f} | {r.get('share', np.nan) * 100:5.1f} | {r.oi / 1e6:6.2f} | {r.fund * 100:+.3f}% | {r.dep2 / 1e3:5.0f}")
    R = pd.DataFrame(rows)
    if len(R):
        print(f"\n  {coin}, неделя перед пампом к фону за 40…15 дней до (раз): сделок {R.pre_n.median():.2f}, оборот {R.pre_vol.median():.2f}, "
              f"средняя сделка {R.pre_avg.median():.2f}, стакан ±2% {R.pre_dep.median():.2f}, ОИ {R.pre_oi.median():.2f}; "
              f"парных: фон {R.base_pair.median():.1%}, неделя до {R.pre_pair.median():.1%}, первые 4 дня пампа {R.on_pair.median():.1%}")
        print(R.round({c: 3 for c in R.columns if c not in ('event', 'top')}).to_string())
    return R


if __name__ == "__main__":
    for c in sys.argv[1:]:
        report(c)
