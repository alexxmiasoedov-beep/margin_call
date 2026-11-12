"""Г6. Вето шорта после каскада ликвидаций (Bian et al.: вынужденные распродажи откатываются; 康文津, 顾明: после
нетто-продаж с плечом следующая неделя доходнее; Gornall et al.: дислокации перпов возвращаются быстро).
Каскад (пороги заданы заранее в отчёте s22): суммарный OI в долларах по 50 самым торгуемым перпам падает на 5%+ за
час или быстрее, а BTC — на 3%+. OI и цена BTC — 5-мин метрики data.binance.vision (s20/metrics; цена = OI $ / OI в
монетах). Сумма OI — по одним и тем же монетам в обеих точках (монета без данных не даёт ложного провала). Каскады
ближе суток друг к другу — один.
Затем сделки журналов, открытые в 24 и 72 ч после каскада, против остальных: бэктесты s20 (4260 сделок шести журналов),
💸 (как в боте, s21/repay_wide.journal) и ↩️ (s21/repay_hold.journal). Запуск из папки с данными."""
import glob
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import CUT, DAY, UTC

STEP = 300


def series(sym):
    fs = sorted(glob.glob(f"s20/metrics/{sym}/*.npy"))
    a = [np.load(f) for f in fs]
    a = [x for x in a if len(x)]
    if not a:
        return None
    a = np.concatenate(a); a = a[np.argsort(a[:, 0])]
    return a


def cascades():
    top = open("s22/top50.txt").read().split()
    S = {s: series(s) for s in top}
    S = {s: a for s, a in S.items() if a is not None}
    t0 = min(a[0, 0] for a in S.values()); t1 = max(a[-1, 0] for a in S.values())
    grid = np.arange(t0 // STEP * STEP, t1 + STEP, STEP)
    M = np.full((len(S), len(grid)), np.nan)
    for n, a in enumerate(S.values()):
        i = ((a[:, 0] - grid[0]) // STEP).astype(int)
        ok = (i >= 0) & (i < len(grid)) & (a[:, 2] > 0)
        M[n, i[ok]] = a[ok, 2]
    b = S["BTC"]; P = np.full(len(grid), np.nan)
    i = ((b[:, 0] - grid[0]) // STEP).astype(int); ok = (b[:, 1] > 0)
    P[i[ok]] = b[ok, 2] / b[ok, 1]
    drop = np.zeros(len(grid)); bdrop = np.zeros(len(grid))
    for k in range(1, 13):
        cur, prev = M[:, k:], M[:, :-k]
        m = np.isfinite(cur) & np.isfinite(prev)
        num, den = np.where(m, cur, 0).sum(0), np.where(m, prev, 0).sum(0)
        r = np.where(den > 0, num / den - 1, 0.0)
        drop[k:] = np.minimum(drop[k:], r)
        pb = P[k:] / P[:-k] - 1
        bdrop[k:] = np.minimum(bdrop[k:], np.nan_to_num(pb, nan=0.0))
    hit = (drop <= -0.05) & (bdrop <= -0.03)
    ev, last = [], -1e18
    for t, d, bd in zip(grid[hit], drop[hit], bdrop[hit]):
        if t - last >= DAY:
            ev.append((int(t), d, bd)); last = t
    cover = np.isfinite(M).sum(0)
    return pd.DataFrame(ev, columns=["t", "oi", "btc"]), (grid, cover, len(S))


def flag(te, C, hours):
    tc = np.sort(C.t.values)
    j = np.searchsorted(tc, te, "left") - 1
    return (j >= 0) & (te - tc[np.maximum(j, 0)] <= hours * 3600) & (te > tc[np.maximum(j, 0)])


if __name__ == "__main__":
    C, (grid, cover, n) = cascades()
    print(f"монет в сумме OI: {n}; 5-мин точек {len(grid):,} ({pd.to_datetime(grid[0], unit='s').date()} — "
          f"{pd.to_datetime(grid[-1], unit='s').date()}), в среднем монет с данными {cover.mean():.0f}")
    print(f"каскадов: {len(C)}")
    for r in C.itertuples():
        print(f"  {pd.to_datetime(r.t, unit='s'):%Y-%m-%d %H:%M} UTC: OI {r.oi * 100:+.1f}%, BTC {r.btc * 100:+.1f}%")
    C.to_pickle("s22/h6_cascades.pkl")

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s21"))
    import repay_hold, repay_wide
    T = pd.read_pickle("s20/trades.pkl")[["journal", "s", "te", "net"]]
    rw = repay_wide.journal(repay_wide.mask(), sl=0.5, hold=168)
    rp = repay_hold.journal(repay_hold.signals(), 0.10, 0.25, 48)
    T = pd.concat([T, pd.DataFrame(dict(journal="💸", s=rw.s, te=rw["T"], net=rw.net)),
                   pd.DataFrame(dict(journal="↩️", s=rp.s, te=rp["T"], net=rp.net))], ignore_index=True)
    T = T[(T.te >= grid[0] + DAY) & (T.te <= grid[-1])].reset_index(drop=True)
    print(f"\nСделки журналов в периоде OI: {len(T)}")
    for hrs in (24, 72):
        T[f"w{hrs}"] = flag(T.te.values, C, hrs)
    for hrs in (24, 72):
        w = T[f"w{hrs}"]
        print(f"\nОкно {hrs} ч после каскада: сделок {w.sum()} ({w.mean():.1%})")
        print(f"  все журналы: в окне {T.net[w].mean() * 100:+.2f}% (медиана {T.net[w].median() * 100:+.2f}%, в плюсе "
              f"{(T.net[w] > 0).mean():.0%}), вне окна {T.net[~w].mean() * 100:+.2f}%; сумма сделок в окне {T.net[w].sum() * 100:+.1f}% "
              f"из {T.net.sum() * 100:+.1f}%")
        for j, g in T.groupby("journal"):
            ww = g[f"w{hrs}"]
            if ww.sum() == 0:
                continue
            h1, h2 = g[ww & (g.te < CUT)], g[ww & (g.te >= CUT)]
            print(f"  {j:6s}: в окне {ww.sum():3d} сделок {g.net[ww].mean() * 100:+.2f}% (половины {h1.net.mean() * 100:+.2f}/"
                  f"{h2.net.mean() * 100:+.2f}%), вне окна {g.net[~ww].mean() * 100:+.2f}%; итог без вето {g.net.sum() * 100:+.1f}%, "
                  f"с вето {g.net[~ww].sum() * 100:+.1f}%")
        days = pd.to_datetime(T.te[w], unit="s").dt.date
        top = T[w].groupby(days.values).net.agg(["size", "sum"]).sort_values("sum").head(5)
        print("  самые убыточные дни в окне: " + "; ".join(f"{d} {r['size']:.0f} сделок {r['sum'] * 100:+.0f}%" for d, r in top.iterrows()))
    T.to_pickle("s22/h6_trades.pkl")
