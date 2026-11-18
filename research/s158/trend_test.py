"""s158 — тренд монеты и BTC по 50-дневной средней как фильтр шорта пампов (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Пампы — s154_pumps_<период>.pkl. Т1: цена за 2 ч до входа ниже 50-дневной средней дневных закрытий (сутки до дня входа);
Т2: BTC ниже своей 50-дневной средней. Запуск в папке периода с MC_K: python3 <repo>/research/s158/trend_test.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s157"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400
PER = ("2020–2022", "2022–2024", "2024–2026")


def daily_close(a):
    t = a["t"].astype(np.int64); c = a["c"].astype(float); v = a["qv"] > 0
    d = pd.Series(c[v], index=t[v] // DAY * DAY)
    return d.groupby(level=0).last()


def run(per):
    from common import K  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    F = pd.read_pickle(f"{OUT}/s154_pumps_{per}.pkl")
    btc = daily_close(K["BTC"]); bma = btc.rolling(50).mean()
    cache, t1, t2 = {}, [], []
    for r in F.itertuples():
        if r.s not in cache:
            dc = daily_close(K[r.s]); cache[r.s] = (dc, dc.rolling(50).mean())
        dc, ma = cache[r.s]
        dprev = int(r.t) // DAY * DAY - DAY
        i = idx_at(r.s, int(r.t) - 2 * 3600)
        p0 = float(K[r.s]["c"][i]) if i is not None else np.nan
        m = ma.get(dprev, np.nan)
        t1.append(np.nan if not np.isfinite(m) else float(p0 < m))
        bm, bc = bma.get(dprev, np.nan), btc.get(dprev, np.nan)
        t2.append(np.nan if not np.isfinite(bm) else float(bc < bm))
    F["T1"], F["T2"] = t1, t2
    F.to_pickle(f"{OUT}/s158_{per}.pkl")
    print(per, len(F), "T1 доля", round(float(np.nanmean(t1)), 2), "T2 доля", round(float(np.nanmean(t2)), 2))


def report():
    from opt_test import wdiff  # noqa: E402
    for col, name in (("T1", "памп начался ниже 50-дневной средней (Т1)"), ("T2", "BTC ниже 50-дневной средней (Т2)")):
        print(f"\n{name}")
        A = []
        for per in PER:
            F = pd.read_pickle(f"{OUT}/s158_{per}.pkl").rename(columns={"t": "te"}).dropna(subset=[col]); F["per"] = per; A.append(F)
            for sub, X in (("все пампы", F), ("спот ≥ 26%", F[F.share >= 0.26])):
                a, b = X[X[col] == 1], X[X[col] == 0]; d, t = wdiff(a, b)
                print(f"  {per} {sub:11s}: да {len(a)} {a.net.mean():+.2%} | нет {len(b)} {b.net.mean():+.2%} | разница {d:+.2%} (t {t:+.1f})")
        A = pd.concat(A, ignore_index=True)
        for sub, X in (("все пампы", A), ("спот ≥ 26%", A[A.share >= 0.26])):
            a, b = X[X[col] == 1], X[X[col] == 0]; d, t = wdiff(a, b)
            print(f"  шесть лет {sub}: да {a.net.mean():+.2%} | нет {b.net.mean():+.2%} | разница {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
