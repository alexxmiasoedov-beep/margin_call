"""s88 — проверка вне выборки (01.10.2022–30.09.2024) правила, найденного после расчёта: час 00:00–01:00 UTC (открытие дня
Upbit), фьючерс за час +5% и больше, доля Кореи (Upbit + Bithumb) в обороте часа ≥ 20%, фьючерс торгуется ≥ суток →
шорт в 01:00 UTC; тейк 10 / стоп 25 / 48 ч по часовым свечам (правила как у s15/common.trade). Плацебо — та же монета
за 45/90/135 сут; контроль — те же пороги в другие часы (не чаще раза в сутки на монету). Калибровка — тот же часовой
расчёт на сделках 10.2024–10.2026 (s88/trades.pkl) против 15-минутного. Гипотеза и порог — ВЫВОДЫ.md, записаны до
загрузки данных. Запуск из папки с данными (после oos_fetch.py): python3 <путь>/s88/oos_test.py; MC_Y0=2020 — период
10.2020–09.2022 (s130; калибровку пропускать: --no-cal)."""
import datetime
import glob
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from oi_test import DAY, ct  # noqa: E402

H1 = 3600
FEE = 0.001
Y0 = int(os.environ.get("MC_Y0", "2022"))                  # начало периода: октябрь Y0 (s130: 2020)
OOS0 = int(datetime.datetime(Y0, 10, 1, tzinfo=datetime.timezone.utc).timestamp())
OOS1 = int(datetime.datetime(Y0 + 2, 10, 1, tzinfo=datetime.timezone.utc).timestamp())
MID = int(datetime.datetime(Y0 + 1, 10, 1, tzinfo=datetime.timezone.utc).timestamp())
DIR = "s88/oos" if Y0 == 2022 else f"s88/oos{Y0}"
R_MIN, SH_MIN = 0.05, 0.20
EXITS = {"S_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "S_24h": dict(tp=None, sl=0.15, hold_h=24)}


def trade1h(a, fr, i, tp=None, sl=0.25, hold_h=48, side=-1):
    """Сделка по часовым свечам a (t — начало часа): вход в закрытии свечи i, остальное — как s15/common.trade."""
    t = a["t"]; n = int(hold_h)
    if i < 1 or i + n >= len(t) or t[i + n] != t[i] + n * H1:
        return None
    p0 = float(a["c"][i])
    hi, lo, op = (a[x][i + 1:i + n + 1].astype(float) for x in ("h", "l", "o"))
    adv, fav = (hi, lo) if side < 0 else (lo, hi)
    ks = np.flatnonzero(side * (adv - p0 * (1 - side * sl)) <= 0) if sl else np.array([], int)
    kt = np.flatnonzero(side * (fav - p0 * (1 + side * tp)) >= 0) if tp else np.array([], int)
    k_s = int(ks[0]) if len(ks) else n
    k_t = int(kt[0]) if len(kt) else n
    if k_s < n and k_s <= k_t:
        stop = p0 * (1 - side * sl)
        px = (max(stop, op[k_s]) * 1.002) if side < 0 else (min(stop, op[k_s]) * 0.998)
        xi = i + 1 + k_s
    elif k_t < n:
        px, xi = p0 * (1 + side * tp), i + 1 + k_t
    else:
        px, xi = float(a["c"][i + n]), i + n
    t0, t1 = float(t[i]) + H1, float(t[xi]) + H1
    f = float(fr[(fr[:, 0] > t0) & (fr[:, 0] <= t1), 1].sum()) if len(fr) else 0.0
    return side * (px / p0 - 1) - side * f - FEE


def load_oos():
    mp = pickle.load(open(f"{DIR}/map.pkl", "rb"))
    F = {os.path.basename(p)[:-4]: x for p in glob.glob(f"{DIR}/fut/*.pkl") if (x := pickle.load(open(p, "rb")))}
    KC = {}
    for p in glob.glob(f"{DIR}/kc/*/*.pkl"):
        x = pickle.load(open(p, "rb"))
        if x:
            KC[(p.split("/")[-2], os.path.basename(p)[4:-4])] = x
    return mp, F, KC


def panel(mp, F, KC):
    """Строки «монета × час»: t (начало часа), r1, доля Кореи; индекс i — часовая свеча фьючерса."""
    btc, kbtc = F["BTCUSDT"], KC[("upbit", "BTC")]
    rate = pd.Series(kbtc["c"], index=kbtc["t"]) / pd.Series(btc["c"], index=btc["t"])
    rate = rate.dropna()
    out = {}
    for b, sym in mp.items():
        a = F.get(sym)
        if a is None or len(a["t"]) < 48:
            continue
        t = a["t"]
        kv = np.zeros(len(t))
        has = False
        for ex in ("upbit", "bithumb"):
            x = KC.get((ex, b))
            if x is None:
                continue
            has = True
            v = pd.Series(x["v"], index=x["t"]).reindex(t).fillna(0.0).values
            r = rate.reindex(np.union1d(rate.index, t)).ffill().bfill().reindex(t).values
            kv += v / r
        if not has:
            continue
        qv = a["qv"].astype(float)
        live0 = t[np.flatnonzero(qv > 0)[0]] if (qv > 0).any() else np.inf
        prev_ok = np.r_[False, t[1:] - t[:-1] == H1]
        r1 = np.r_[np.nan, a["c"][1:] / a["c"][:-1] - 1]
        d = pd.DataFrame({"t": t, "i": np.arange(len(t)), "r1": np.where(prev_ok, r1, np.nan),
                          "share": kv / np.maximum(kv + qv, 1.0), "qv": qv})
        d = d[(d.qv > 0) & (d.t >= live0 + DAY)]
        out[sym] = d
    return out


def events(P, F):
    rows = []
    for sym, d in P.items():
        a = F[sym]; fr = a["f"]
        x = d[(d.r1 >= R_MIN) & (d.share >= SH_MIN) & (d.t + H1 >= OOS0) & (d.t + H1 < OOS1)]
        last = -10 ** 18
        for H, i, r1, sh in zip(x.t.values, x.i.values, x.r1.values, x.share.values):
            open9 = H % DAY == 0
            if not open9:
                if H - last < DAY:
                    continue
                last = H
            r = dict(s=sym, t=int(H) + H1, open9=open9, r1=r1, share=sh)
            for nm, kw in EXITS.items():
                r[nm] = trade1h(a, fr, int(i), **kw)
                pl = []
                for dd in (45, 90, 135):
                    k = np.searchsorted(a["t"], H - dd * DAY)
                    if k < len(a["t"]) and a["t"][k] == H - dd * DAY and a["qv"][k] > 0:
                        y = trade1h(a, fr, int(k), **kw)
                        if y is not None:
                            pl.append(y)
                r["pl_" + nm] = np.mean(pl) if pl else np.nan
            rows.append(r)
    X = pd.DataFrame(rows)
    for nm in EXITS:
        X[nm] = X[nm].astype(float)
    return X


def line(lab, x0, col, months, cut=MID):
    x = x0[x0[col].notna()]
    if len(x) < 8:
        print(f"  {lab:36s} {col:7s} n={len(x)}")
        return None
    m, t, n = ct(x[col], x.t); dp, tp, _ = ct((x[col] - x["pl_" + col]).dropna(), x.t[(x[col] - x["pl_" + col]).notna()])
    h1, h2 = x[x.t < cut], x[x.t >= cut]
    (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
    print(f"  {lab:36s} {col:7s} n={n:5d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
          f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
          f" разница {dp:+6.2%} (t {tp:+4.1f})")
    return m, (abs(m / t) if t else np.nan)


def calibration():
    """Сделки 10.2024–10.2026 (s88/trades.pkl, час открытия, ≥ 5%, ≥ 20%): 15-мин расчёт против часового."""
    from common import K, funding, live  # noqa: E402
    X = pd.read_pickle("s88/trades.pkl")
    X = X[X.open9 & (X.r1 >= R_MIN) & (X.share >= SH_MIN)]
    res, cache = [], {}
    for s, T, v in zip(X.s, X.t, X.S_10_25):
        if s in cache:
            b = cache[s]
            k = np.searchsorted(b["t"], T - H1)
            if k < len(b["t"]) and b["t"][k] == T - H1:
                y = trade1h(b, funding(s), int(k), tp=0.10, sl=0.25, hold_h=48)
                if y is not None and np.isfinite(v):
                    res.append((v, y, T))
            continue
        a = K[s]; t = a["t"]
        lo, hi = live(s)
        g = (t // H1) * H1
        ok = (t >= lo) & (t <= hi)
        df = pd.DataFrame({"g": g[ok], "o": a["o"][ok].astype(float), "h": a["h"][ok].astype(float),
                           "l": a["l"][ok].astype(float), "c": a["c"][ok].astype(float)})
        agg = df.groupby("g").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("o", "size"))
        agg = agg[agg.n == 4]
        b = {"t": agg.index.values.astype(np.int64), "o": agg.o.values, "h": agg.h.values, "l": agg.l.values, "c": agg.c.values}
        cache[s] = b
        k = np.searchsorted(b["t"], T - H1)
        if k < len(b["t"]) and b["t"][k] == T - H1:
            y = trade1h(b, funding(s), int(k), tp=0.10, sl=0.25, hold_h=48)
            if y is not None and np.isfinite(v):
                res.append((v, y, T))
    R = pd.DataFrame(res, columns=["m15", "h1", "t"])
    print(f"Калибровка на 10.2024–10.2026: {len(R)} сделок; 15 мин {R.m15.mean():+.2%}, по часам {R.h1.mean():+.2%};"
          f" совпадение знака {(np.sign(R.m15) == np.sign(R.h1)).mean():.0%}, корреляция {R.m15.corr(R.h1):.2f}")


def main():
    mp, F, KC = load_oos()
    P = panel(mp, F, KC)
    X = events(P, F)
    X.to_pickle(f"{DIR}_trades.pkl")
    months = (OOS1 - OOS0) / (30.4 * DAY)
    A, O = X[X.open9], X[~X.open9]
    print(f"Вне выборки 01.10.{Y0}–30.09.{Y0 + 2}: монет с фьючерсом и рынком к воне {len(P)};"
          f" событий на открытии {len(A)} ({len(A) / months:.1f} в месяц), в другие часы {len(O)}")
    for col in EXITS:
        print(f"\n{col}")
        ra = line("открытие дня Upbit (правило)", A, col, months)
        ro = line("другие часы", O, col, months)
        if ra and ro:
            d = ra[0] - ro[0]; se = np.hypot(ra[1], ro[1])
            print(f"  разница открытие − другие часы: {d:+6.2%} (t {d / se:+4.1f})")
    x = A.copy(); x["q"] = pd.to_datetime(x.t, unit="s").dt.to_period("Q")
    print("\nПо кварталам (открытие, S_10_25):\n" + x.groupby("q").S_10_25.agg(["count", "mean"]).round(4).to_string())
    print("\nДля отчёта: рост 5–7% и ≥ 7% на открытии")
    line("рост 5–7%", A[A.r1 < 0.07], "S_10_25", months)
    line("рост ≥ 7%", A[A.r1 >= 0.07], "S_10_25", months)
    if "--no-cal" not in sys.argv:                            # калибровке нужен архив 15-мин свечей (много памяти)
        print()
        calibration()


if __name__ == "__main__":
    main()
