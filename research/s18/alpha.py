"""Binance Alpha перед фьючерсом: когда у токена Alpha (ончейн-рынок в кошельке Binance) появляется фьючерс USDT-M и что
происходит с ценой фьючерса после запуска. Данные: список Alpha (публичный bapi, s18/alpha.json: время листинга в Alpha),
15-мин свечи фьючерсов из ветки data (s2/k2y.pkl, по 18.10.2026; начало торгов — первая свеча с объёмом, common.live).
Токенизированные акции (stockState / rwaInfo) исключены.

Сравнение: новые фьючерсы токенов Alpha против новых фьючерсов без Alpha (крипто: часовая волатильность первых трёх
суток ≥ 1,5%, чтобы отсеять фьючерсы на акции и сырьё) и против рынка — медианы шорта всех торгующихся фьючерсов за то же
окно. Сделки — как у 🇰🇷🆕 и вариант из research/s3: шорт через 1 ч / 24 ч после запуска, 7 суток, стоп 50%.
Запуск из папки с данными: python3 s18/alpha.py"""
import datetime
import json
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import BAR, K, live, trade

UTC = datetime.timezone.utc
A0 = datetime.datetime(2024, 10, 2, tzinfo=UTC).timestamp()          # фьючерсы, начавшиеся позже начала архива
END = datetime.datetime(2026, 10, 10, tzinfo=UTC).timestamp()        # чтобы хватило свечей на 7 суток
SYMS = list(K)


def alpha_tokens():
    d = json.load(open("s18/alpha.json"))["data"]
    out = []
    for x in d:
        if x.get("stockState") or x.get("rwaInfo") or not x.get("listingTime"):
            continue
        names = {str(x.get("symbol") or "").upper(), str(x.get("cexCoinName") or "").upper()} - {""}
        out.append(dict(names=names, t=x["listingTime"] / 1000, chain=x.get("chainName"), addr=x.get("contractAddress"),
                        cex=bool(x.get("listingCex")), delisted=bool(x.get("fullyDelisted"))))
    return out


def fut_for(names):
    for n in names:
        for p in ("", "1000", "1000000"):
            if p + n in K:
                return p + n
    return None


def hvol(s, i0, bars=288):
    c = K[s]["c"][i0:i0 + bars].astype(float)
    if len(c) < 40:
        return np.nan
    h = c[::4]
    return float(np.std(np.diff(np.log(h)))) if len(h) > 10 else np.nan


def market(t0, t1):
    r = []
    for s in SYMS:
        t = K[s]["t"]
        if t[0] > t0 or t[-1] < t1:
            continue
        i0, i1 = np.searchsorted(t, t0), np.searchsorted(t, t1)
        if t[i0] == t0 and t[i1] == t1 and K[s]["qv"][i0] > 0 and K[s]["qv"][i1] > 0:
            r.append(1 - float(K[s]["c"][i1]) / float(K[s]["c"][i0]))
    return float(np.median(r)) if len(r) > 50 else np.nan


if __name__ == "__main__":
    A = alpha_tokens()
    amap = {}
    for a in A:
        s = fut_for(a["names"])
        if s and (s not in amap or a["t"] < amap[s]["t"]):
            amap[s] = a
    print(f"токенов Alpha без акций: {len(A)}; с фьючерсом Binance (по 18.10.2026): {len(amap)}")
    rows = []
    for s in SYMS:
        lo, hi = live(s)
        if not (A0 <= lo <= END):
            continue
        t = K[s]["t"]; i0 = int(np.searchsorted(t, lo))
        a = amap.get(s)
        rows.append(dict(s=s, launch=lo, alpha=a is not None, lag_d=(lo - a["t"]) / 86400 if a else np.nan,
                         chain=a["chain"] if a else None, addr=a["addr"] if a else None, cex=a["cex"] if a else None, hv=hvol(s, i0), i0=i0))
    L = pd.DataFrame(rows)
    L["crypto"] = L.hv >= 0.015
    print(f"новых фьючерсов 02.10.2024–10.10.2026: {len(L)}, из них крипто (волатильность ≥ 1,5%/ч) {int(L.crypto.sum())}, "
          f"токенов Alpha {int(L.alpha.sum())}")
    a = L[L.alpha]
    print("задержка «фьючерс − листинг в Alpha», сутки:", {k: int(v) for k, v in pd.cut(a.lag_d, [-1e9, -30, -1, 1, 7, 30, 1e9],
          labels=["фьючерс раньше > 30 сут", "раньше 1–30 сут", "в те же сутки (±1)", "позже 1–7 сут", "позже 7–30 сут", "позже > 30 сут"]).value_counts().sort_index().items()})

    print("\nпуть цены после запуска (шорт, только цена; к рынку — минус медиана шорта всех фьючерсов за то же окно):")
    for grp, m in (("Alpha", L.alpha & L.crypto), ("не Alpha, крипто", ~L.alpha & L.crypto)):
        g = L[m]
        for start_h in (1, 24):
            parts = []
            for h in (24, 72, 168, 336):
                v, mk = [], []
                for r in g.itertuples():
                    t = K[r.s]["t"]; c = K[r.s]["c"]; i = r.i0 + 4 * start_h; k = i + 4 * h
                    if k < len(t) and t[k] == t[i] + 4 * h * BAR and K[r.s]["qv"][i] > 0:
                        x = 1 - float(c[k]) / float(c[i]); v.append(x)
                        mk.append(x - market(float(t[i]), float(t[k])))
                v, mk = np.array(v), np.array(mk)
                parts.append(f"{h} ч: {np.mean(v) * 100:+.1f}% (медиана {np.median(v) * 100:+.1f}%), к рынку {np.nanmean(mk) * 100:+.1f}%")
            print(f"  {grp:16s} n={len(g):3d}, вход через {start_h:2d} ч | " + " | ".join(parts))

    print("\nсделка: шорт, 7 суток без тейка, стоп 50% (комиссия 0,1% и фандинг):")
    for grp, m in (("Alpha", L.alpha & L.crypto), ("не Alpha, крипто", ~L.alpha & L.crypto),
                   ("Alpha: фьючерс в те же сутки", L.alpha & L.crypto & (L.lag_d.abs() <= 1)),
                   ("Alpha: фьючерс позже > 1 сут", L.alpha & L.crypto & (L.lag_d > 1)),
                   ("Alpha: фьючерс раньше > 1 сут", L.alpha & L.crypto & (L.lag_d < -1))):
        for start_h in (1, 24):
            R = pd.DataFrame([dict(x, t=r.launch) for r in L[m].itertuples() if (x := trade(r.s, r.i0 + 4 * start_h, sl=0.5, hold_h=168))])
            if not len(R):
                continue
            h = R.t < R.t.median()
            print(f"  {grp:30s} вход через {start_h:2d} ч: n={len(R):3d}, {R.net.mean() * 100:+5.1f}% на сделку (медиана {R.net.median() * 100:+5.1f}%), "
                  f"в плюсе {(R.net > 0).mean():.0%}, стопов {(R.why == 'стоп').mean():.0%}, 1-я/2-я половина {R.net[h].mean() * 100:+.1f}/{R.net[~h].mean() * 100:+.1f}%")
    L.to_pickle("s18/launches.pkl")
