"""s93 — закрытые фиатные рынки Азии (Indodax IDR, Bitkub THB, CoinDCX INR; свечи — fetch.py). Гипотезы — ВЫВОДЫ.md,
записаны до загрузки данных:
H1 — листинг: монета с фьючерсом Binance старше суток впервые торгуется к местной валюте → шорт с закрытия первого часа,
     7 сут со стопом 50% (основной) и 10 / 25 / 48 ч; одна сделка на монету за 7 сут (первая из бирж);
H2 — пятёрка по обороту за 24 ч на бирже (без 10 лидеров первой половины и стейблкоинов), впервые за 7 сут → шорт 10/25/48;
     основная группа — без входов 🔝 и 👀 за 7 сут, 🇰🇷 и 🛒 за сутки;
H3 — памп (s15/kr_pumps.pkl) с долей трёх бирж ≥ 10% в обороте последнего полного часа (вместе с фьючерсом Binance) →
     шорт 10/25/48; основная группа — как в H2.
Плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными: python3 <путь>/s93/asia_test.py"""
import glob
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

H1h = 3600
EXS = ("indodax", "bitkub", "coindcx")
STABLE = {"USDT", "USDC", "FDUSD", "TUSD", "DAI", "BUSD", "USDE", "USD1", "PYUSD"}
EX7 = dict(tp=None, sl=0.50, hold_h=168)
EX48 = dict(tp=0.10, sl=0.25, hold_h=48)
T0 = 1727740800


def load():
    D = {}
    for ex in EXS:
        d = {}
        for p in glob.glob(f"s93/c/{ex}/*.pkl"):
            a = pickle.load(open(p, "rb"))
            if len(a):
                d[os.path.basename(p)[:-4]] = a
        D[ex] = d
    return D


def usd_volume(D):
    """{биржа: {монета: Series оборот в $ по часам}} — объём в монете × закрытие / курс USDT к местной валюте."""
    out = {}
    for ex, d in D.items():
        if "USDT" not in d:
            continue
        fx = pd.Series(d["USDT"][:, 1], index=d["USDT"][:, 0].astype(np.int64))
        o = {}
        for c, a in d.items():
            if c == "USDT":
                continue
            t = a[:, 0].astype(np.int64)
            r = fx.reindex(np.union1d(fx.index, t)).ffill().bfill().reindex(t).values
            o[c] = pd.Series(a[:, 2] * a[:, 1] / r, index=t)
        out[ex] = o
    return out


def overlaps():
    S65 = pd.read_pickle("s65/trades.pkl"); S83 = pd.read_pickle("s83/trades.pkl")
    S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl")
    kl = S20[S20.journal == "🇰🇷🆕"]; S20 = S20[S20.journal == "🇰🇷"]
    wk, dy, kn = {}, {}, {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S83.s, S83.t)):
        wk.setdefault(s, []).append(t)
    for s, t in list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        dy.setdefault(s, []).append(t)
    for s, t in zip(kl.s, kl.te):
        kn.setdefault(s, []).append(t)
    f = lambda m: {s: np.array(v, float) for s, v in m.items()}
    return f(wk), f(dy), f(kn)


def ov(s, T, wk, dy):
    a, b = wk.get(s, np.zeros(0)), dy.get(s, np.zeros(0))
    return bool(((a <= T) & (a >= T - 7 * DAY)).any() or ((b <= T) & (b >= T - DAY)).any())


def deal(s, T, exits):
    i = idx_at(s, T)
    if i is None:
        return None
    r = {}
    for nm, kw in exits.items():
        y = trade(s, i, **kw)
        r[nm] = y["net"] if y else np.nan
        p = [z["net"] for dd in (45, 90, 135) if (k := idx_at(s, T - dd * DAY)) is not None and (z := trade(s, k, **kw))]
        r["pl_" + nm] = np.mean(p) if p else np.nan
    return r


def line(lab, x0, col, months):
    x = x0[x0[col].notna()]
    if len(x) < 8:
        print(f"  {lab:40s} {col:7s} n={len(x)}")
        return
    m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
    h1, h2 = x[x.t < CUT], x[x.t >= CUT]
    print(f"  {lab:40s} {col:7s} n={n:5d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
          f" половины {ct(h1[col], h1.t)[0]:+6.2%} (t {ct(h1[col], h1.t)[1]:+4.1f}) / {ct(h2[col], h2.t)[0]:+6.2%}"
          f" (t {ct(h2[col], h2.t)[1]:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")


def main():
    D = load(); V = usd_volume(D); wk, dy, kn = overlaps()
    months = 24.6
    print("Пар со свечами: " + ", ".join(f"{ex} {len(d)}" for ex, d in D.items()))
    # H1 — листинги
    ev = []
    for ex, d in D.items():
        for c, a in d.items():
            if c in STABLE:
                continue
            s, _ = fut_of(c)
            t0 = int(a[0, 0])
            if not s or s not in K or t0 <= T0 + 7 * DAY or live(s)[0] + DAY > t0:
                continue
            ev.append((t0, ex, c, s))
    ev.sort(); rows, last = [], {}
    for t0, ex, c, s in ev:
        if t0 - last.get(s, -1e18) < 7 * DAY:
            continue
        last[s] = t0
        r = deal(s, t0 + H1h, {"S_7d": EX7, "S_10_25": EX48})
        if r:
            k = kn.get(s, np.zeros(0))
            v = V.get(ex, {}).get(c)                             # проверка после расчёта: настоящий листинг — всплеск оборота
            day1 = float(v[(v.index >= t0) & (v.index < t0 + DAY)].sum()) if v is not None else 0.0
            later = v[(v.index >= t0 + DAY) & (v.index < t0 + 30 * DAY)] if v is not None else None
            med = float(later.groupby(later.index // DAY).sum().median()) if later is not None and len(later) else 0.0
            rows.append(dict(s=s, t=t0 + H1h, ex=ex, kr=bool((np.abs(k - t0) <= 3 * DAY).any()), burst=day1 >= 2 * med, **r))
    L = pd.DataFrame(rows); L.to_pickle("s93/h1.pkl")
    print(f"\nH1 — листинги: {len(L)} ({len(L) / months:.1f} в месяц); по биржам {L.ex.value_counts().to_dict()};"
          f" в ±3 сут от корейского листинга {L.kr.mean():.0%}")
    for col in ("S_7d", "S_10_25"):
        line("все (основная)", L, col, months)
        line("без корейского листинга ±3 сут", L[~L.kr], col, months)
        line("после расчёта: со всплеском оборота в 1-е сутки", L[L.burst], col, months)
        for ex in EXS:
            line(f"  {ex}", L[L.ex == ex], col, months)
    # H2 — пятёрка по обороту
    rows = []
    for ex, o in V.items():
        idx = np.arange(T0, 1792540800, H1h)
        M = pd.DataFrame({c: s.reindex(idx).fillna(0.0).values for c, s in o.items() if c not in STABLE}, index=idx)
        M24 = M.rolling(24, min_periods=24).sum()
        maj = set(M24[M24.index < CUT].median().nlargest(10).index)
        R = M24.drop(columns=[c for c in maj if c in M24]).rank(axis=1, ascending=False, method="first")
        top = (R <= 5) & (M24.drop(columns=[c for c in maj if c in M24]) > 0)
        in7 = top.rolling(168, min_periods=1).max().shift(1).fillna(0).astype(bool)
        new = top & ~in7
        lastc = {}
        for T, row in new.iterrows():
            for c in row.index[row.values]:
                s, _ = fut_of(c)
                Tc = int(T) + H1h                              # конец часа
                if not s or s not in K or live(s)[0] + DAY > Tc or Tc - lastc.get(c, -1e18) < 7 * DAY:
                    continue
                lastc[c] = Tc
                r = deal(s, Tc, {"S_10_25": EX48, "S_7d": EX7})
                if r:
                    rows.append(dict(s=s, t=Tc, ex=ex, ov=ov(s, Tc, wk, dy), **r))
    T2 = pd.DataFrame(rows); T2.to_pickle("s93/h2.pkl")
    print(f"\nH2 — пятёрка по обороту: {len(T2)} событий; без журналов {(~T2.ov).sum()} ({(~T2.ov).sum() / months:.1f} в месяц)")
    for col in ("S_10_25", "S_7d"):
        line("без журналов (основная)", T2[~T2.ov], col, months)
        line("все", T2, col, months)
        for ex in EXS:
            line(f"  {ex}, без журналов", T2[(T2.ex == ex) & ~T2.ov], col, months)
    # H3 — доля трёх бирж в пампе
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    loc = {}
    for ex, o in V.items():
        for c, s_ in o.items():
            fs, _ = fut_of(c)
            if fs:
                loc[fs] = s_ if fs not in loc else loc[fs].add(s_, fill_value=0.0)
    rows = []
    for s, js in PU.items():
        if s not in loc:
            continue
        a = K[s]; t = a["t"]; qv = a["qv"].astype(float); lv = loc[s]
        for j in js:
            T = int(t[j]) + 900; he = T // H1h * H1h; hs = he - H1h
            b = float(qv[np.searchsorted(t, hs):np.searchsorted(t, he)].sum())
            v = float(lv.get(hs, 0.0))
            sh = v / max(v + b, 1.0)
            if sh < 0.10:
                continue
            r = deal(s, T, {"S_10_25": EX48})
            if r:
                rows.append(dict(s=s, t=T, share=sh, ov=ov(s, T, wk, dy), **r))
    P3 = pd.DataFrame(rows); P3.to_pickle("s93/h3.pkl")
    print(f"\nH3 — доля трёх бирж в пампе ≥ 10%: {len(P3)} пампов; без журналов {(~P3.ov).sum()}")
    line("без журналов (основная)", P3[~P3.ov], "S_10_25", months)
    line("все", P3, "S_10_25", months)


if __name__ == "__main__":
    main()
