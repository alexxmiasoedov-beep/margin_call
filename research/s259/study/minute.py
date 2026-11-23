"""s259, вопрос 1 (минутный срез) — насколько индекс Binance повторяет ход перпа в ту же минуту и за сколько минут догоняет:
настоящий indexPriceKlines и klines перпа 1 мин из архива data.binance.vision за один месяц (MONTH) у выборки перпов:
без спота с перпом в составе индекса (вес ≥ 0,2 по снимку s252), без спота без перпа в индексе, монеты со спотом при близком
обороте. Скачанное разбирается в памяти, на диск не пишется. Механика, не сделки.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/minute.py"""
import io
import json
import os
import pickle
import sys
import time
import urllib.parse
import urllib.request
import zipfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import OUT  # noqa: E402

UA = {"User-Agent": "research-script/1.0"}
MONTH = os.environ.get("MONTH", "2026-09")
N = int(os.environ.get("NPER", "12"))


def fetch(sym, kind):
    s = urllib.parse.quote(f"{sym}USDT")
    url = f"https://data.binance.vision/data/futures/um/monthly/{kind}/{s}/1m/{s}-1m-{MONTH}.zip"
    for k in range(3):
        try:
            time.sleep(0.3)
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines():
                p = ln.split(",")
                if p and p[0].isdigit():
                    rows.append((int(p[0]) // 1000, float(p[4]), float(p[7]) if len(p) > 7 and kind == "klines" else 0.0))
            return pd.DataFrame(rows, columns=["t", "c", "qv"]).drop_duplicates("t").set_index("t")
        except Exception as e:  # noqa: BLE001
            print("сбой", sym, kind, e, flush=True)
            time.sleep(3 * (k + 1))
    return None


def sample():
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    U = json.load(open(f"{OUT}/universe.json"))
    m0 = pd.Timestamp(MONTH + "-01", tz="UTC").timestamp(); m1 = m0 + 30 * 86400
    vol = {}
    for s, u in U.items():
        a = K[s]; m = (a["t"] >= m0) & (a["t"] < m1)
        if m.sum() > 2700 and (a["qv"][m] > 0).mean() > 0.99:
            vol[s] = float(a["qv"][m].sum())
    ns = [s for s in vol if U[s]["snap"] and U[s]["spot0"] is None]
    selfy = sorted([s for s in ns if U[s].get("self", 0) >= 0.2], key=vol.get, reverse=True)[:N]
    noself = sorted([s for s in ns if U[s].get("self", 0) == 0], key=vol.get, reverse=True)[:N]
    med = np.median([vol[s] for s in selfy + noself])
    sp = [s for s in vol if U[s]["spot0"] and U[s]["spot0"] < m0 - 90 * 86400]
    spot = sorted(sp, key=lambda s: abs(np.log(vol[s] / med)))[:N]
    return {"сам перп в индексе (вес ≥ 0,2)": selfy, "перпа в индексе нет": noself, "со спотом, близкий оборот": spot}, U


def stats(c, i):
    df = pd.concat([c.c.rename("p"), i.c.rename("i")], axis=1).dropna()
    df = df[df.index.to_series().diff() == 60]
    rp = np.log(df.p).diff().dropna(); ri = np.log(df.i).diff().reindex(rp.index)
    ok = np.isfinite(ri)
    rp, ri = rp[ok], ri[ok]
    beta0 = np.cov(ri, rp)[0, 1] / np.var(rp)
    lag = {L: np.cov(ri.values[L:], rp.values[:len(rp) - L])[0, 1] / np.var(rp) for L in (1, 2, 3, 5)}
    lead = np.cov(rp.values[1:], ri.values[:-1])[0, 1] / np.var(ri)            # перп за индексом через минуту
    gap = np.log(df.p / df.i)
    big = np.flatnonzero(np.abs(rp.values) >= 0.02)
    resp = {k: [] for k in (0, 1, 2, 5, 15)}
    lp, li = np.log(df.p).reindex(rp.index).values, np.log(df.i).reindex(rp.index).values
    for b in big:
        if b < 1 or b + 15 >= len(lp):
            continue
        dp = lp[b] - lp[b - 1]
        for k in resp:
            resp[k].append((li[b + k] - li[b - 1]) / dp)
    return dict(beta0=beta0, lag=lag, lead=lead, gap_abs=float(np.median(np.abs(gap))), gap90=float(np.quantile(np.abs(gap), .9)),
                n_big=len(big), resp={k: float(np.median(v)) if v else np.nan for k, v in resp.items()})


def main():
    G, U = sample()
    rows = []
    for g, syms in G.items():
        for s in syms:
            c = fetch(s, "klines"); i = fetch(s, "indexPriceKlines")
            if c is None or i is None or not len(c) or not len(i):
                continue
            r = stats(c, i)
            rows.append(dict(group=g, s=s, self=U[s].get("self", np.nan), alpha=U[s].get("alpha", np.nan), **{k: v for k, v in r.items() if k not in ("lag", "resp")},
                             **{f"lag{k}": v for k, v in r["lag"].items()}, **{f"resp{k}": v for k, v in r["resp"].items()}))
            print(f"{g}: {s} β0 {r['beta0']:.2f}, лаги 1/2/3/5 мин {', '.join(f'{v:.2f}' for v in r['lag'].values())}; "
                  f"|перп/индекс − 1| медиана {r['gap_abs']:.2%}, 90% {r['gap90']:.2%}; ходов перпа ≥ 2% за минуту {r['n_big']}, "
                  f"индекс прошёл 0/1/2/5/15 мин: {', '.join(f'{v:.0%}' for v in r['resp'].values())}", flush=True)
    X = pd.DataFrame(rows)
    print(f"\n=== месяц {MONTH}, медианы по группам")
    cols = ["beta0", "lag1", "lag2", "lag3", "lag5", "lead", "gap_abs", "gap90", "n_big", "resp0", "resp1", "resp2", "resp5", "resp15"]
    print(X.groupby("group")[cols].median().round(3).to_string())
    print("\nкорреляция β0 с весом перпа в индексе (без спота):",
          round(X[X.group != "со спотом, близкий оборот"][["beta0", "self"]].corr().iloc[0, 1], 2))


if __name__ == "__main__":
    main()
