"""s183 — «стоимость» по сети: капитализация к активным адресам (Cong и др.; Borri и др. CVALUE — цена к новым адресам)
по бесплатному Coin Metrics Community API (без ключа). Только охват: у скольких ликвидных альтов есть ряд AdrActCnt
по периодам и распределение лог(капитализация / активные адреса за 7 сут). Доходы не считаются.

Запуск: python3 -I cm_value.py   Кэш: /home/user/mc_data/s183/cm/<актив>.json"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402
from coverage import load  # noqa: E402

API = "https://community-api.coinmetrics.io/v4"
UA = {"User-Agent": "research-script/1.0"}
CACHE = f"{C.OUT}/cm"


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:      # нет доступа без ключа или нет ряда — без повтора
                return None
            time.sleep(10 * (k + 1))
        except Exception as e:  # сеть: пауза и повтор
            print("  сбой", type(e).__name__, url[:90], flush=True)
            time.sleep(10 * (k + 1))
    return None


def catalog(metric):
    d = get(f"{API}/catalog-all/metrics?metrics={metric}")
    for m in (d or {}).get("data", []):
        for f in m["frequencies"]:
            if f["frequency"] == "1d":
                return set(f["assets"])
    return set()


def series(asset, metric):
    os.makedirs(CACHE, exist_ok=True)
    p = f"{CACHE}/{asset}_{metric}.json"
    if os.path.exists(p):
        return json.load(open(p))
    rows, url = [], (f"{API}/timeseries/asset-metrics?assets={asset}&metrics={metric}&frequency=1d"
                     f"&start_time=2020-06-01&end_time=2026-11-01&page_size=10000")
    while url:
        d = get(url)
        if d is None:
            return None
        rows += [(x["time"][:10], float(x[metric])) for x in d.get("data", []) if x.get(metric) is not None]
        url = d.get("next_page_url")
        time.sleep(1.0)
    json.dump(rows, open(p, "w"))
    return rows


def main():
    act = catalog("AdrActCnt")
    new = catalog("AdrNewCnt")
    print("Coin Metrics Community: активов с AdrActCnt (1d)", len(act), "| с AdrNewCnt (1d)", len(new), flush=True)
    perps = set()
    for per in C.PERS:
        X = load(per)
        perps |= set(X[X.liq5.astype(bool)].s)
    mp = {}
    for s in sorted(perps):
        b = C.base(s).lower()
        for cand in (b, b + "_eth"):
            if cand in act:
                mp[s] = cand
                break
    print("ликвидных перпов (за все периоды)", len(perps), "| с рядом активных адресов", len(mp), flush=True)
    A = {}
    for s, a in mp.items():
        r = series(a, "AdrActCnt")
        if r:
            z = pd.Series({C.ts(d): v for d, v in r})
            A[s] = z
    pd.to_pickle(A, f"{C.OUT}/cm_adr.pkl")
    for per in C.PERS:
        X = load(per)
        L = X[X.liq5.astype(bool)].copy()
        vals = []
        for r in L.itertuples():
            z = A.get(r.s)
            if z is None or not np.isfinite(r.mcap):
                vals.append(np.nan); continue
            w = z[(z.index >= r.d0 - 7 * C.DAY) & (z.index < r.d0)]
            vals.append(np.log(r.mcap / w.mean()) if len(w) >= 5 and w.mean() > 0 else np.nan)
        L["lp_aa"] = vals
        g = L[L.lp_aa.notna()].groupby("d0").size().reindex(L.d0.unique(), fill_value=0)
        q = L.lp_aa.dropna().quantile([0.05, 0.5, 0.95]).values if L.lp_aa.notna().any() else [np.nan] * 3
        print(f"{per}: ликвидных альтов с капитализацией CMC и активными адресами на срез — медиана {g.median():.0f} "
              f"(мин {g.min()}, макс {g.max()}); доля от ликвидных {L.lp_aa.notna().mean():.0%}; "
              f"лог(кап./адреса) p5/p50/p95 {q[0]:.1f} / {q[1]:.1f} / {q[2]:.1f}", flush=True)
        L[["d0", "s", "lp_aa"]].to_pickle(f"{C.OUT}/cm_value_{per}.pkl")


if __name__ == "__main__":
    main()
