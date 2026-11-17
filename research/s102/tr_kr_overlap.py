"""s102 — вопрос владельца 17.11: «когда приходит сигнал и турецкого набега, и корейского шорта на одну монету, её выбивает
по стопу в обоих журналах». Сделки обоих журналов за два года пересобраны одним кодом (s15/common.trade: стоп по худшей из
цены стопа и открытия свечи плюс 0,2%, комиссия 0,1%, фактический фандинг):
- 🇹🇷 — правило s2/rush.py (доля пары к лире за час ≥ 10% и ≥ 3× медианы часовых долей за 7 сут, рост за 4 ч > 10%,
  оборот за час ≥ 200 тыс. $, пара старше 8 сут, одна сделка на монету за 48 ч), тейк 10 / стоп 15 / 24 ч;
  свечи пар к лире — s102/try_fetch.py;
- 🇰🇷 — входы журнала из s20/trades.pkl (1173), тейк 10 / стоп 25 / 48 ч.
Совпадение — та же монета и входы обоих журналов не дальше W часов друг от друга.
Запуск из папки с данными: python3 <repo>/research/s102/tr_kr_overlap.py"""
import json
import os
import sys

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as sw

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

T0, T1 = pd.Timestamp("2024-10-19", tz="UTC").timestamp(), pd.Timestamp("2026-10-15", tz="UTC").timestamp()
MONTHS = [f"2024-{m:02d}" for m in (10, 11, 12)] + [f"2025-{m:02d}" for m in range(1, 13)] + \
         [f"2026-{m:02d}" for m in range(1, 11)]


def series(pair):
    a = [np.load(f"s15/try/{pair}-{m}.npy") for m in MONTHS if os.path.exists(f"s15/try/{pair}-{m}.npy")]
    a = [x for x in a if len(x)]
    if not a:
        return None
    a = np.concatenate(a); a = a[np.argsort(a[:, 0])]
    _, u = np.unique(a[:, 0], return_index=True)
    return a[u]


def roll(x, w):
    cs = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)]); out = np.full(len(x), np.nan); out[w - 1:] = cs[w:] - cs[:-w]
    return out


def tr_events():
    """Входы 🇹🇷 по правилу s2/rush.py events(0.10, 3, 0.10, 1.0): (монета, индекс свечи входа, доля, рост за 4 ч)."""
    pairs = json.load(open("s102/try_pairs.json")); fx = series("USDTTRY")
    out = []
    for s, pair in pairs.items():
        b = series(pair); a = K.get(s)
        if b is None or a is None:
            continue
        t = a["t"]; n = len(t); tv = np.zeros(n)
        idx = np.searchsorted(t, b[:, 0]); ok = idx < n; ok[ok] &= t[idx[ok]] == b[ok, 0]
        tv[idx[ok]] = b[ok, 2] / np.interp(b[ok, 0], fx[:, 0], fx[:, 1])
        fq = a["qv"].astype(np.float64); c = a["c"].astype(np.float64)
        t1 = roll(tv, 4); f1 = roll(fq, 4); sh = t1 / np.maximum(t1 + f1, 1)
        med = np.full(n, np.nan)
        if n > 700:
            hourly = sh[3::4]; m = np.full(len(hourly), np.nan)
            m[168:] = np.median(sw(hourly[:-1], 168)[:len(hourly) - 168], axis=1)
            med[3::4] = m
            med = pd.Series(med).ffill().values
        r4 = np.full(n, np.nan); r4[16:] = c[16:] / c[:-16] - 1
        te = t + 900
        okk = (sh >= 0.10) & (sh >= 3 * np.maximum(med, 1e-4)) & (r4 > 0.10) & (r4 <= 1.0) & (f1 + t1 >= 200e3) & \
              (te >= T0) & (te <= T1) & (te > b[0, 0] + 8 * DAY)
        last = -10 ** 9
        for j in np.flatnonzero(okk):
            if j - last >= 192:
                out.append((s, int(j), float(sh[j]), float(r4[j]))); last = j
    return out


def deal(s, i, tp, sl, h):
    r = trade(s, i, tp, sl, h)
    return (r["net"], r["why"]) if r else (np.nan, None)


def main():
    rows = []
    for s, j, sh, r4 in tr_events():
        net, why = deal(s, j, 0.10, 0.15, 24)
        rows.append(dict(j="🇹🇷", s=s, t=float(K[s]["t"][j] + 900), net=net, why=why, sh=sh, r4=r4))
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    for s, te in zip(S20.s, S20.te):
        i = idx_at(s, te)
        net, why = deal(s, i, 0.10, 0.25, 48) if i is not None else (np.nan, None)
        rows.append(dict(j="🇰🇷", s=s, t=float(te), net=net, why=why))
    X = pd.DataFrame(rows).dropna(subset=["net"])
    X["stop"] = X.why == "стоп"
    X.to_pickle("s102/trades.pkl")
    months = (T1 - T0) / (30.4 * DAY)
    for jj in ("🇹🇷", "🇰🇷"):
        x = X[X.j == jj]; m, t, n = ct(x.net, x.t)
        print(f"{jj}: {n} сделок ({n / months:.1f} в мес.), {m:+.2%} (t {t:+.1f}), стопов {x.stop.mean():.0%}, тейков {(x.why == 'тейк').mean():.0%}")
    TR, KR = X[X.j == "🇹🇷"].reset_index(drop=True), X[X.j == "🇰🇷"].reset_index(drop=True)
    kr_by = {s: g for s, g in KR.groupby("s")}
    for W in (1, 6, 24):
        pair_rows = []
        TR[f"ov{W}"] = False; KR[f"ov{W}"] = False
        for a, r in TR.iterrows():
            g = kr_by.get(r.s)
            if g is None:
                continue
            d = (g.t - r.t).abs() <= W * 3600
            if d.any():
                TR.at[a, f"ov{W}"] = True; KR.loc[g.index[d], f"ov{W}"] = True
                b = g[d].iloc[(g[d].t - r.t).abs().argmin()]
                pair_rows.append(dict(s=r.s, tT=r.t, tK=b.t, nT=r.net, nK=b.net, sT=r.stop, sK=b.stop))
        P = pd.DataFrame(pair_rows)
        print(f"\n=== совпадение: та же монета, входы не дальше {W} ч ===")
        print(f"пар: {len(P)} ({len(P) / months:.1f} в мес.); 🇹🇷 первым в {(P.tT < P.tK).mean():.0%}, одновременно (≤ 15 мин) в "
              f"{((P.tT - P.tK).abs() <= 900).mean():.0%}")
        print(f"  обе по стопу: {(P.sT & P.sK).mean():.0%} пар; хотя бы одна: {(P.sT | P.sK).mean():.0%}; "
              f"сумма пары {P.nT.mean() + P.nK.mean():+.2%} (t {ct(P.nT + P.nK, P.tT)[1]:+.1f})")
        for jj, D in (("🇹🇷", TR), ("🇰🇷", KR)):
            for lab, x in (("совпали", D[D[f"ov{W}"]]), ("остальные", D[~D[f"ov{W}"]])):
                m, t, n = ct(x.net, x.t)
                h1, h2 = x[x.t < CUT], x[x.t >= CUT]
                print(f"  {jj} {lab:9s} n={n:4d} {m:+6.2%} (t {t:+4.1f}) стопов {x.stop.mean():4.0%} тейков "
                      f"{(x.why == 'тейк').mean():4.0%} | половины {ct(h1.net, h1.t)[0]:+6.2%} (стопов {h1.stop.mean():3.0%})"
                      f" / {ct(h2.net, h2.t)[0]:+6.2%} (стопов {h2.stop.mean():3.0%})")
            x, y = D[D[f"ov{W}"]], D[~D[f"ov{W}"]]
            # разница средних: t по кластерам дней через объединённую выборку с центровкой
            z = pd.concat([x.assign(g=1), y.assign(g=0)])
            dm = x.net.mean() - y.net.mean()
            se = np.sqrt(x.net.var() / len(x) + y.net.var() / len(y))
            print(f"     разница {jj}: {dm:+.2%} (t ≈ {dm / se:+.1f}); стопов {x.stop.mean() - y.stop.mean():+.0%}")
        if W == 6:
            P.to_pickle("s102/pairs6.pkl")


if __name__ == "__main__":
    main()
