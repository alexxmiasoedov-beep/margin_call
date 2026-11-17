"""s118 — 🇹🇷 вне выборки 10.2022–09.2024: правило s2/rush.py, как в s102/tr_kr_overlap.tr_events (доля пары к лире за час
≥ 10% и ≥ 3× медианы часовых долей за 7 сут, рост за 4 ч > 10%, оборот за час ≥ 200 тыс. $, пара старше 8 сут, одна сделка
на монету за 48 ч), тейк 10 / стоп 15 / 24 ч. Свечи пар к лире за 2022–2024 гг. докачиваются в s15/try (s102/try_fetch.month).
Запуск из ~/mc_oos: MC_K=… MC_F=… MC_CUT=2023-10-01 python3 <repo>/research/s118/tr_oos.py"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s102"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import try_fetch  # noqa: E402
import tr_kr_overlap as tr  # noqa: E402
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

OOS = [f"2022-{m:02d}" for m in (10, 11, 12)] + [f"2023-{m:02d}" for m in range(1, 13)] + [f"2024-{m:02d}" for m in range(1, 10)]


def main():
    os.makedirs("s15/try", exist_ok=True); os.makedirs("s102", exist_ok=True)
    pairs = json.load(open(os.path.join(os.environ.get("MC_DATA", "/home/user/mc_data"), "s102/try_pairs.json")))
    pairs = {s: p for s, p in pairs.items() if s in K}
    json.dump(pairs, open("s102/try_pairs.json", "w"))
    jobs = [(p, m) for p in sorted(set(pairs.values())) + ["USDTTRY"] for m in OOS]
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda j: try_fetch.month(*j), jobs))
    tr.MONTHS = OOS
    tr.T0 = pd.Timestamp("2022-10-01", tz="UTC").timestamp(); tr.T1 = pd.Timestamp("2024-09-28", tz="UTC").timestamp()
    rows = []
    for s, j, sh, r4 in tr.tr_events():
        x = trade(s, j, 0.10, 0.15, 24)
        if x:
            rows.append(dict(s=s, t=float(K[s]["t"][j] + 900), net=x["net"], why=x["why"]))
    X = pd.DataFrame(rows)
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    m, t, n = ct(X.net, X.t); h1, h2 = X[X.t < CUT], X[X.t >= CUT]
    print(f"🇹🇷 вне выборки: пар с фьючерсом {len(pairs)}; сделок {n} ({n / months:.1f} в мес.), {m:+.2%} (t {t:+.1f}), "
          f"в плюсе {(X.net > 0).mean():.0%}, стопов {(X.why == 'стоп').mean():.0%}; половины {h1.net.mean():+.2%} ({len(h1)}) / "
          f"{h2.net.mean():+.2%} ({len(h2)})")
    q = pd.to_datetime(X.t, unit="s").dt.to_period("Q")
    print("по кварталам: " + " ".join(f"{k}:{g.net.mean():+.2%}({len(g)})" for k, g in X.groupby(q)))
    X.to_pickle("s118_tr.pkl")


if __name__ == "__main__":
    main()
