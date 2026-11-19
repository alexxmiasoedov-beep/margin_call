"""s210 — ширина внимания Hyperliquid (Г2 s209): разных трейдеров монеты за сутки ≥ 2,5 × медианы 7 сут и ≥ 100 → шорт перпа
Binance с 00:15 UTC следующих суток, 48 ч, стоп 25%. Контроль — всплеск оборота без всплеска трейдеров.
Запись до расчёта — ВЫВОДЫ.md (коммит b3ad849).

Запуск из /home/user/mc_data:
  python3 run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024
  python3 run.py report
"""
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, OUT = 86400, "/home/user/mc_data"
HL = f"{OUT}/s209/hl"


def series(name, col):
    d = json.load(gzip.open(f"{HL}/{name}.json.gz", "rt"))
    x = pd.DataFrame(d["chart_data"] if isinstance(d, dict) else d)
    x["day"] = pd.to_datetime(x.time).dt.normalize()
    return x.pivot_table(index="day", columns="coin", values=col, aggfunc="sum").sort_index()


def events():
    U = series("daily_unique_users_by_coin", "daily_unique_users")
    V = series("daily_usd_volume_by_coin", "daily_usd_volume").reindex(index=U.index, columns=U.columns)
    mu = U.shift(1).rolling(7, min_periods=7).median()
    mv = V.shift(1).rolling(7, min_periods=7).median()
    ru, rv = U / mu, V / mv
    out = []
    for coin in U.columns:
        u, r, q = U[coin].values, ru[coin].values, rv[coin].values
        days = U.index
        last_w = last_c = -10 ** 9
        for i in range(len(days)):
            if np.isfinite(r[i]) and r[i] >= 2.5 and u[i] >= 100:
                if i - last_w >= 7:
                    out.append((coin, days[i], "wide", float(r[i]), float(q[i]) if np.isfinite(q[i]) else np.nan))
                last_w = i if i - last_w >= 7 else last_w
            elif np.isfinite(q[i]) and q[i] >= 2.5 and np.isfinite(r[i]) and r[i] < 1.5:
                if i - last_c >= 7:
                    out.append((coin, days[i], "volonly", float(r[i]), float(q[i])))
                    last_c = i
    E = pd.DataFrame(out, columns=["coin", "day", "kind", "ru", "rv"])
    E["entry"] = [int(pd.Timestamp(d).tz_localize("UTC").timestamp()) + DAY + 900 for d in E.day]
    return E


def perp_key(K, coin):
    if coin.startswith("k") and coin[1:2].isupper():
        c = "1000" + coin[1:]
        if c in K:
            return c
    return coin if coin in K else None


def run(per):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    E = events()
    E["perp"] = [perp_key(K, c) for c in E.coin]
    E = E[E.perp.notna() & (E.entry >= t0) & (E.entry < t1)]
    res = []
    for (kind, s), g in E.groupby(["kind", "perp"]):
        t = K[s]["t"].astype(np.int64)
        lo, _ = FB.live(s)
        g = g.sort_values("entry").copy()
        st = g.entry.values - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st) & (I >= 96)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        g, I = g[ok].copy(), I[ok]
        if not len(g):
            continue
        okt, net, stp, bars, tend = FB.trades(s, I, 0.25, 48, -1)
        g["net"] = np.where(okt, net, np.nan)
        g["stop"] = np.where(okt, stp, False)
        g["tend"] = tend
        g["hed"] = g.net.values + FB.alt_mv(t[I] + 900, tend)
        g["pl"] = FB.placebo(s, I, 0.25, 48, -1)
        g["t"] = g.entry
        res.append(g)
    R = pd.concat(res, ignore_index=True)
    R["per"] = per
    R.to_pickle(f"{OUT}/s210_{per}.pkl")
    print(per, R[R.net.notna()].groupby("kind").size().to_dict(), flush=True)


def one_per_coin(x):
    keep = []
    for s, g in x.sort_values("t").groupby("perp"):
        last = -1
        for i, r in zip(g.index, g.itertuples()):
            if r.t >= last:
                keep.append(i)
                last = r.tend
    return x.loc[keep]


def line(C, x, cut, months):
    if len(x) < 5:
        return f"n={len(x)}"
    m, t, n = C.ct(x.net, x.t)
    mh, th, _ = C.ct(x.hed, x.t)
    md, td, _ = C.ct(x.net - x.pl, x.t)
    return (f"n={n:4d} ({n / months:5.1f}/мес) {m:+.2%} (t {t:+.1f}) | половины {x[x.t < cut].net.mean():+.2%} / "
            f"{x[x.t >= cut].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f}) | "
            f"стопов {x.stop.mean():.0%}")


def report():
    import common182 as C  # noqa: E402
    print("s210 — ширина внимания Hyperliquid → шорт перпа Binance 48 ч, стоп 25%\n")
    win = {"2022–2024": ("2023-06-21", "2024-10-01", "2024-02-01"), "2024–2026": ("2024-10-01", "2026-04-05", "2025-07-01")}
    pn, ph, pdl = [], [], []
    for per in ("2022–2024", "2024–2026"):
        R = pd.read_pickle(f"{OUT}/s210_{per}.pkl")
        R = R[R.net.notna()]
        a, b, cut = (C.ts(x) for x in win[per])
        mo = (b - a) / (30.4 * DAY)
        R = R[(R.t >= a) & (R.t < b)]
        x = one_per_coin(R[R.kind == "wide"])
        c = one_per_coin(R[R.kind == "volonly"])
        print(f"== {per} (окно {win[per][0]} — {win[per][1]}, {mo:.1f} мес) ==")
        print(f"  основной: трейдеров ≥ ×2,5: {line(C, x, cut, mo)}")
        print(f"  контроль: оборот ≥ ×2,5 без трейдеров: {line(C, c, cut, mo)}")
        print(f"  доза ×3: {line(C, one_per_coin(R[(R.kind == 'wide') & (R.ru >= 3)]), cut, mo)}")
        print(f"  доза ×5: {line(C, one_per_coin(R[(R.kind == 'wide') & (R.ru >= 5)]), cut, mo)}")
        y = pd.concat([x.assign(g=1), c.assign(g=0)])
        d, se = C.diff(y.net, y.g == 1, y.t)
        pdl.append((d, se, len(y)))
        print(f"  Δ ширина − оборот без ширины: {d:+.2%} (t {d / se:+.1f})")
        m, t, n = C.ct(x.net, x.t)
        mh, th, _ = C.ct(x.hed, x.t)
        pn.append((m, abs(m / t) if t else np.nan, n))
        ph.append((mh, abs(mh / th) if th else np.nan, n))
        if per == "2024–2026":
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            crit = [("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                    ("сверх плацебо > 0", (x.net - x.pl).mean() > 0), ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
        print()
    m, t = C.combine(pn)
    mh, th = C.combine(ph)
    print(f"Два окна, основной: {m:+.2%} (t {t:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f})")
    print("  по окнам: " + " / ".join(f"{a:+.2%}" for a, _, _ in pn) + "; с хеджем " + " / ".join(f"{a:+.2%}" for a, _, _ in ph))
    d, t = C.combine(pdl)
    print(f"Δ ширина − оборот без ширины вместе: {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1])
