"""s99 — «полночь Bithumb»: час 15:00–16:00 UTC (00:00 по Корее, Bithumb обнуляет дневное изменение), фьючерс за час +5%
и больше, доля Bithumb в обороте часа ≥ 20% → шорт в 16:00 UTC, 10 / 25 / 48 ч. Контроль — другие часы, плацебо — та же
монета за 45/90/135 сут. Основная история — 15-мин свечи (s2) и часовые свечи Bithumb (s15/kr_candles_bithumb.pkl);
вне выборки 10.2022–09.2024 — часовые данные s88/oos и часовой расчёт сделки (s88/oos_test.trade1h).
Гипотеза — ВЫВОДЫ.md, записана до расчёта. Запуск из папки с данными: python3 <путь>/s99/midnight_test.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s88"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402
import oos_test as O  # noqa: E402

H1 = 3600
OPEN_H = 16 * H1                                     # конец часа 15:00–16:00 UTC
R_MIN, SH_MIN = 0.05, 0.20
EX = {"S_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "S_24h": dict(tp=None, sl=0.15, hold_h=24)}


def overlaps():
    S65 = pd.read_pickle("s65/trades.pkl"); S83 = pd.read_pickle("s83/trades.pkl")
    S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    S88 = pd.read_pickle("s88/trades.pkl"); S88 = S88[S88.open9 & (S88.r1 >= 0.05) & (S88.share >= 0.20)]
    wk, dy = {}, {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S83.s, S83.t)):
        wk.setdefault(s, []).append(t)
    for s, t in list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)) + list(zip(S88.s, S88.t)):
        dy.setdefault(s, []).append(t)
    return {s: np.array(v, float) for s, v in wk.items()}, {s: np.array(v, float) for s, v in dy.items()}


def in_sample():
    C = pickle.load(open("s15/kr_candles_bithumb.pkl", "rb"))
    fx = pd.Series(C["USDT"]["c"].astype(float), index=C["USDT"]["t"])
    wk, dy = overlaps()
    rows = []
    for coin, x in C.items():
        if coin == "USDT":
            continue
        s, mult = fut_of(coin)
        if not s or s not in K:
            continue
        a = K[s]; t = a["t"]; c = a["c"].astype(float); qv = a["qv"].astype(float)
        lo, hi = live(s)
        kt = x["t"]; kv = x["v"].astype(float)
        rate = fx.reindex(np.union1d(fx.index, kt)).ffill().bfill().reindex(kt).values
        kusd = pd.Series(kv / rate, index=kt)
        j = np.flatnonzero((t + 900) % H1 == 0)                    # 15-мин свечи, закрывающиеся в начале часа
        j = j[(j >= 4)]
        j = j[t[j - 4] == t[j] - H1]
        T = t[j] + 900
        r1 = c[j] / c[j - 4] - 1
        cs = np.r_[0.0, np.cumsum(qv)]
        bvol = cs[j + 1] - cs[j - 3]
        bv = kusd.reindex(T - H1).fillna(0.0).values
        share = bv / np.maximum(bv + bvol, 1.0)
        ok = (r1 >= R_MIN) & (share >= SH_MIN) & (T >= lo + DAY) & (T <= hi) & (bvol > 0)
        last = -10 ** 18
        for jj, TT, rr, sh in zip(j[ok], T[ok], r1[ok], share[ok]):
            mid = TT % DAY == OPEN_H
            if not mid:
                if TT - last < DAY:
                    continue
                last = TT
            w, d = wk.get(s, np.zeros(0)), dy.get(s, np.zeros(0))
            r = dict(s=s, t=int(TT), mid=mid, r1=rr, share=sh,
                     ov=bool(((w <= TT) & (w >= TT - 7 * DAY)).any() or ((d <= TT) & (d >= TT - DAY)).any()))
            for nm, kw in EX.items():
                y = trade(s, int(jj), **kw)
                r[nm] = y["net"] if y else np.nan
                p = [z["net"] for dd in (45, 90, 135) if (k := idx_at(s, TT - dd * DAY)) is not None and (z := trade(s, k, **kw))]
                r["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(r)
    return pd.DataFrame(rows)


def out_of_sample():
    mp, F, KC = O.load_oos()
    btc, kbtc = F["BTCUSDT"], KC[("upbit", "BTC")]
    rate = (pd.Series(kbtc["c"], index=kbtc["t"]) / pd.Series(btc["c"], index=btc["t"])).dropna()
    rows = []
    for b, sym in mp.items():
        a = F.get(sym); x = KC.get(("bithumb", b))
        if a is None or x is None or len(a["t"]) < 48:
            continue
        t = a["t"]; qv = a["qv"].astype(float)
        r = rate.reindex(np.union1d(rate.index, t)).ffill().bfill().reindex(t).values
        kv = pd.Series(x["v"], index=x["t"]).reindex(t).fillna(0.0).values / r
        live0 = t[np.flatnonzero(qv > 0)[0]] if (qv > 0).any() else np.inf
        prev_ok = np.r_[False, t[1:] - t[:-1] == H1]
        r1 = np.where(prev_ok, np.r_[np.nan, a["c"][1:] / a["c"][:-1] - 1], np.nan)
        share = kv / np.maximum(kv + qv, 1.0)
        idx = np.flatnonzero((r1 >= R_MIN) & (share >= SH_MIN) & (qv > 0) & (t >= live0 + DAY)
                             & (t + H1 >= O.OOS0) & (t + H1 < O.OOS1))
        last = -10 ** 18
        for i in idx:
            H = int(t[i]); mid = (H + H1) % DAY == OPEN_H
            if not mid:
                if H - last < DAY:
                    continue
                last = H
            rr = dict(s=sym, t=H + H1, mid=mid)
            for nm, kw in EX.items():
                rr[nm] = O.trade1h(a, a["f"], int(i), **kw)
                pl = []
                for dd in (45, 90, 135):
                    k = np.searchsorted(t, H - dd * DAY)
                    if k < len(t) and t[k] == H - dd * DAY and qv[k] > 0:
                        y = O.trade1h(a, a["f"], int(k), **kw)
                        if y is not None:
                            pl.append(y)
                rr["pl_" + nm] = np.mean(pl) if pl else np.nan
            rows.append(rr)
    X = pd.DataFrame(rows)
    for nm in EX:
        X[nm] = X[nm].astype(float)
    return X


def line(lab, x0, col, months, cut=CUT):
    x = x0[x0[col].notna()]
    if len(x) < 8:
        print(f"  {lab:34s} {col:7s} n={len(x)}")
        return None
    m, t, n = ct(x[col], x.t); dp, tp, _ = ct((x[col] - x["pl_" + col]).values, x.t.values)
    h1, h2 = x[x.t < cut], x[x.t >= cut]
    print(f"  {lab:34s} {col:7s} n={n:5d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
          f" половины {ct(h1[col], h1.t)[0]:+6.2%} (t {ct(h1[col], h1.t)[1]:+4.1f}) / {ct(h2[col], h2.t)[0]:+6.2%}"
          f" (t {ct(h2[col], h2.t)[1]:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")
    return m, (abs(m / t) if t else np.nan)


def compare(A, B, col, months, lab):
    ra = line(f"{lab}: полночь Bithumb", A, col, months)
    rb = line(f"{lab}: другие часы", B, col, months)
    if ra and rb:
        d = ra[0] - rb[0]; se = np.hypot(ra[1], rb[1])
        print(f"  {lab}: полночь − другие часы {d:+6.2%} (t {d / se:+4.1f})")


def main():
    X = in_sample(); X.to_pickle("s99/trades.pkl")
    m = (X.t.max() - X.t.min()) / (30.4 * DAY)
    A, B = X[X.mid], X[~X.mid]
    print(f"Основная история: полночь Bithumb {len(A)} ({len(A) / m:.1f} в месяц), без журналов {(~A.ov).sum()};"
          f" другие часы {len(B)}")
    for col in EX:
        print(f"\n{col}")
        compare(A, B, col, m, "все")
        line("полночь, без журналов", A[~A.ov], col, m)
    Y = out_of_sample(); Y.to_pickle("s99/oos_trades.pkl")
    mo = (O.OOS1 - O.OOS0) / (30.4 * DAY)
    print(f"\nВне выборки 10.2022–09.2024: полночь {Y.mid.sum()} ({Y.mid.sum() / mo:.1f} в месяц), другие часы {(~Y.mid).sum()}")
    for col in EX:
        print(f"\n{col}")
        ra = line("вне выборки: полночь Bithumb", Y[Y.mid], col, mo, cut=O.MID)
        rb = line("вне выборки: другие часы", Y[~Y.mid], col, mo, cut=O.MID)
        if ra and rb:
            d = ra[0] - rb[0]; se = np.hypot(ra[1], rb[1])
            print(f"  вне выборки: полночь − другие часы {d:+6.2%} (t {d / se:+4.1f})")


if __name__ == "__main__":
    main()
