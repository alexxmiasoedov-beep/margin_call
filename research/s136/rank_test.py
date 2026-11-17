"""s136 — первый за 90 сут вход в топ-50/100/200 дневного снимка CoinMarketCap → шорт фьючерса Binance (гипотеза —
ВЫВОДЫ.md, записана до расчёта). Снимки — s136/raw/<дата>.json (cmc_hist.py), снимок за дату D известен в 00:00 UTC D + 1,
вход — закрытие 15-мин свечи 01:00 UTC D + 1, 7 сут, стоп +50%, без тейка (s15/common.trade). Монета CMC → фьючерс:
тикер, 1000тикер или 1000000тикер с проверкой цены (0,8–1,25). Одна сделка на монету за 7 сут. Плацебо — та же монета
за 45/90/135 сут. Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s136/rank_test.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import datetime
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY = 86400
RAW, OUT = "/home/user/mc_data/s136/raw", "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19", "2025-12-01")}
SKIP = {"BTC", "ETH", "USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDP", "USDE", "PYUSD", "USD1", "WBTC", "STETH"}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def events():
    files = sorted(glob.glob(f"{RAW}/*.json"))
    have = {os.path.basename(f)[:-5] for f in files}
    rank, price, sym = {}, {}, {}
    for f in files:
        d = os.path.basename(f)[:-5]
        for cid, s, rk, mc, circ, px, vol in json.load(open(f)):
            rank.setdefault(cid, {})[d] = rk; price.setdefault(cid, {})[d] = px; sym[cid] = s
    ev = []
    for cid, rr in rank.items():
        if sym[cid] in SKIP:
            continue
        for N in (50, 100, 200):
            for d in sorted(x for x, r in rr.items() if r <= N):
                D = datetime.date.fromisoformat(d)
                prev = [str(D - datetime.timedelta(days=k)) for k in range(1, 91)]
                if sum(p in have for p in prev) < 80:
                    continue
                if any(p in rr and rr[p] <= N for p in prev):
                    continue
                ev.append(dict(cid=cid, sym=sym[cid], d=d, N=N, px=price[cid][d], t=ts(d) + DAY + 3600))
    return pd.DataFrame(ev).sort_values("t").reset_index(drop=True)


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    t0, t1, _ = PER[per]
    E = events()
    E = E[(E.t >= ts(t0)) & (E.t < ts(t1))]
    rows, last = [], {}
    for r in E.itertuples():
        key = None
        for p, mult in (("", 1.0), ("1000", 1e3), ("1000000", 1e6)):
            k = p + r.sym
            if k in K:
                i = idx_at(k, r.t - 3600 - DAY)             # цена фьючерса в 00:00 UTC D против цены CMC за D
                if i is not None and r.px and 0.8 <= float(K[k]["c"][i]) / (r.px * mult) <= 1.25:
                    key = k
                break
        if key is None or r.t < last.get(key, -1):
            continue
        lo, _ = live(key)
        if lo + DAY > r.t:
            continue
        i = idx_at(key, r.t)
        x = trade(key, i, tp=None, sl=0.5, hold_h=168, side=-1) if i is not None else None
        if not x:
            continue
        last[key] = r.t + 7 * DAY
        pl = []
        for dd in (45, 90, 135):
            j = idx_at(key, r.t - dd * DAY)
            y = trade(key, j, tp=None, sl=0.5, hold_h=168, side=-1) if j is not None else None
            if y:
                pl.append(y["net"])
        rows.append(dict(s=key, t=r.t, N=r.N, net=x["net"], why=x["why"], pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s136_{per}.pkl")
    print(per, "событий CMC в периоде", len(E), "сделок", len(X))


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s136_{per}.pkl"); X["per"] = per; X["cut"] = ts(cut)
        A.append(X)
        months = (ts(t1) - ts(t0)) / (30.4 * DAY)
        for lab, x in [("все пороги", X)] + [(f"топ-{n}", X[X.N == n]) for n in (50, 100, 200)]:
            if len(x) < 8:
                print(f"{per} {lab:10s} n={len(x)}"); continue
            m, t, n = ct(x.net, x.t); dp = (x.net - x.pl).dropna()
            md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
            print(f"{per} {lab:10s} n={n:4d} ({n / months:4.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(x.net > 0).mean():.0%} "
                  f"стопов {(x.why == 'стоп').mean():.0%} | половины {x[x.t < x.cut].net.mean():+.2%} / "
                  f"{x[x.t >= x.cut].net.mean():+.2%} | сверх плацебо {md:+.2%} (t {td:+.1f})")
    A = pd.concat(A, ignore_index=True)
    m, t, n = ct(A.net, A.t); dp = (A.net - A.pl).dropna(); md, td, _ = ct(dp, A.t[(A.net - A.pl).notna()])
    print(f"шесть лет: n={n} {m:+.2%} (t {t:+.1f}), сверх плацебо {md:+.2%} (t {td:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
