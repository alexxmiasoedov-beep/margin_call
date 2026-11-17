"""s134 — режим «корейской мании» по кимчи-премии BTC (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Премия за час: KRW-BTC Upbit ÷ USD/KRW ЕЦБ (api.frankfurter.dev) ÷ BTCUSDT фьючерса Binance − 1; за день — среднее по
часам; P14 — средняя за 14 полных суток до дня входа. Сделки журналов:
- 2024–2026 гг. — s103/beta_trades.pkl (все журналы, доход r);
- 2022–2024 гг. — ⏰ s88/oos_trades.pkl, 🇰🇷 ~/mc_oos/s118_kr.pkl (kr ≥ 20%), 🛒 ~/mc_oos/s118_spot.pkl (доля спота ≥ 25,9%),
  🇹🇷 ~/mc_oos/s118_tr.pkl;
- 2020–2022 гг. — ⏰ s88/oos2020_trades.pkl, 🇰🇷 ~/mc_2020/s118_kr.pkl, 🛒 ~/mc_2020/s118_spot2020.pkl.
Запуск из /home/user/mc_data: python3 <repo>/research/s134/premium.py"""
import io
import json
import os
import pickle
import sys
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import ct  # noqa: E402

DAY, H1 = 86400, 3600
KOR = ["⏰", "🇰🇷", "🛒", "🔝", "👀"]                     # корейские журналы и журналы пампов
VIS = "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-{}.zip"
UA = {"User-Agent": "research-script/1.0"}


def http(url):
    for i in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception:
            time.sleep(3 * (i + 1))
    raise RuntimeError(url)


def usdkrw():
    p = "s134/usdkrw.json"
    if not os.path.exists(p):
        rates = {}
        for y in range(2020, 2027):
            x = json.loads(http(f"https://api.frankfurter.dev/v1/{y}-01-01..{y}-12-31?from=USD&to=KRW"))
            rates.update({d: v["KRW"] for d, v in x["rates"].items()})
            time.sleep(1)
        os.makedirs("s134", exist_ok=True)
        json.dump(rates, open(p, "w"))
    r = json.load(open(p))
    s = pd.Series(r).rename(index=pd.Timestamp).sort_index()
    return s.reindex(pd.date_range(s.index[0], "2026-11-17", freq="D")).ffill()


def btc_hourly():
    parts = []
    for d in ("s88/oos2020", "s88/oos"):
        f = pickle.load(open(f"{d}/fut/BTCUSDT.pkl", "rb"))
        parts.append(pd.Series(f["c"].astype(float), index=f["t"].astype(np.int64)))
    p = "s134/btc_2024.pkl"
    if not os.path.exists(p):
        rows = []
        for m in pd.period_range("2024-09", "2026-10", freq="M"):
            z = zipfile.ZipFile(io.BytesIO(http(VIS.format(m))))
            for ln in z.read(z.namelist()[0]).decode().splitlines():
                q = ln.split(",")
                if q[0].isdigit():
                    rows.append((int(q[0]) // 1000, float(q[4])))
        pd.Series(dict(rows)).to_pickle(p)
    parts.append(pd.read_pickle(p))
    s = pd.concat(parts)
    return s[~s.index.duplicated(keep="last")].sort_index()


def krw_btc_hourly():
    parts = []
    for d in ("s88/oos2020", "s88/oos"):
        x = pickle.load(open(f"{d}/kc/upbit/KRW-BTC.pkl", "rb"))
        parts.append(pd.Series(x["c"].astype(float), index=x["t"].astype(np.int64)))
    x = pickle.load(open("s15/kr_candles_upbit.pkl", "rb"))["BTC"]
    parts.append(pd.Series(x["c"].astype(float), index=x["t"].astype(np.int64)))
    s = pd.concat(parts)
    return s[~s.index.duplicated(keep="last")].sort_index()


def premium_daily():
    fx = usdkrw()
    k, b = krw_btc_hourly(), btc_hourly()
    j = k.index.intersection(b.index)
    day = pd.to_datetime(j, unit="s").normalize()
    pr = k.loc[j].values / fx.reindex(day).values / b.loc[j].values - 1
    return pd.Series(pr, index=day).groupby(level=0).mean()


def trades():
    T = []
    B = pd.read_pickle("s103/beta_trades.pkl")
    T.append(pd.DataFrame({"j": B.j, "t": B.t.astype(float), "net": B.r, "per": "2024–2026"}))
    for per, f in (("2020–2022", "s88/oos2020_trades.pkl"), ("2022–2024", "s88/oos_trades.pkl")):
        X = pd.read_pickle(f); X = X[X.open9 & (X.r1 >= 0.05) & (X.share >= 0.20) & X.S_10_25.notna()]
        T.append(pd.DataFrame({"j": "⏰", "t": X.t.astype(float), "net": X.S_10_25, "per": per}))
    for per, d, sp in (("2020–2022", "/home/user/mc_2020", "s118_spot2020.pkl"), ("2022–2024", "/home/user/mc_oos", "s118_spot.pkl")):
        A = pd.read_pickle(f"{d}/s118_kr.pkl"); A = A[A.kr >= 0.20]
        T.append(pd.DataFrame({"j": "🇰🇷", "t": A.t.astype(float), "net": A.net, "per": per}))
        S = pd.read_pickle(f"{d}/{sp}"); S = S[S.share >= 0.259]
        T.append(pd.DataFrame({"j": "🛒", "t": S.t.astype(float), "net": S.net, "per": per}))
    R = pd.read_pickle("/home/user/mc_oos/s118_tr.pkl")
    T.append(pd.DataFrame({"j": "🇹🇷", "t": R.t.astype(float), "net": R.net, "per": "2022–2024"}))
    X = pd.concat(T, ignore_index=True)
    return X[X.net.notna()]


def diff(a, b):
    """Разница средних a − b и t по средним за день входа (сделки одного дня зависимы)."""
    da = a.groupby(pd.to_datetime(a.t, unit="s").dt.date).net.mean()
    db = b.groupby(pd.to_datetime(b.t, unit="s").dt.date).net.mean()
    d = a.net.mean() - b.net.mean()
    se = np.sqrt(da.var() / len(da) + db.var() / len(db))
    return d, d / se if se > 0 else np.nan


def main():
    P = premium_daily()
    P14 = P.rolling(14, min_periods=10).mean().shift(1)            # 14 полных суток до дня входа
    print("премия BTC по годам (среднее, доля дней ≥ 2%):")
    for y, x in P.groupby(P.index.year):
        print(f"  {y}: {x.mean():+.2%}, P14 ≥ 2% у {(P14[P14.index.year == y] >= 0.02).mean():.0%} дней")
    X = trades()
    X["day"] = pd.to_datetime(X.t, unit="s").dt.normalize()
    X["p14"] = P14.reindex(X.day).values
    X["mania"] = X.p14 >= 0.02
    print(f"\nсделок {len(X)}, P14 известна у {X.p14.notna().mean():.0%}")
    print(f"\n{'журнал':6s} {'период':10s} {'мания':>22s} {'обычный':>22s}")
    for (j, per), x in X.groupby(["j", "per"]):
        a, b = x[x.mania], x[~x.mania & x.p14.notna()]
        print(f"{j:6s} {per:10s} {len(a):5d}: {a.net.mean():+6.2%}{'':8s} {len(b):5d}: {b.net.mean():+6.2%}")
    K = X[X.j.isin(KOR) & X.p14.notna()]
    print("\nКорейские журналы и журналы пампов вместе (⏰ 🇰🇷 🛒 🔝 👀):")
    for per, x in list(K.groupby("per")) + [("все периоды", K)]:
        a, b = x[x.mania], x[~x.mania]
        if len(a) >= 5 and len(b) >= 5:
            d, t = diff(a, b)
            ma, ta, _ = ct(a.net, a.t); mb, tb, _ = ct(b.net, b.t)
            print(f"  {per:12s} мания {len(a):5d}: {ma:+.2%} (t {ta:+.1f}) | обычный {len(b):5d}: {mb:+.2%} (t {tb:+.1f})"
                  f" | разница {d:+.2%} (t {t:+.1f})")
        else:
            print(f"  {per:12s} мания {len(a)}, обычный {len(b)}")
    C = X[(X.j == "🇹🇷") & X.p14.notna()]
    if len(C):
        a, b = C[C.mania], C[~C.mania]
        print(f"\nконтроль 🇹🇷: мания {len(a)}: {a.net.mean():+.2%} | обычный {len(b)}: {b.net.mean():+.2%}")
    X.to_pickle("s134_trades.pkl")


if __name__ == "__main__":
    main()
