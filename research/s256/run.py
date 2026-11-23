"""s256 — 🛒 для перпов без спота Binance: доля Binance Alpha в обороте пампа (правило проверки — ВЫВОДЫ.md, записано до
расчёта). Пампы — s15/kr_pumps.pkl (+15% за ≤ 2 ч из покоя, свечи s2/k2y.pkl), шорт с закрытия свечи пампа 10/25/48 ч,
одна сделка на монету за 48 ч, плацебо — та же монета за 45/90/135 сут (как s49). Доля Alpha = оборот Alpha / (Alpha +
перп) за последний полный час до закрытия свечи пампа; свечи Alpha — s256/alpha/<перп>.json (fetch.py). Перп без спота
Binance на момент пампа — как в s253 (s252/spot_dates.json, s23/spot1h.pkl).
Запуск из /home/user/mc_data: python3 <repo>/research/s256/run.py [count|main]"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
DAY, WEEK = 86400, 7 * 86400
SH = 0.26                                          # порог доли 🛒 — только для отчёта
EX = dict(tp=0.10, sl=0.25, hold_h=48)
T0 = pd.Timestamp("2024-10-01", tz="UTC").timestamp()
T1 = pd.Timestamp("2026-10-19", tz="UTC").timestamp()


def wk(t):
    return (np.asarray(t, np.int64) // WEEK) * WEEK


def ct(x, t):
    x = np.asarray(x, float); w = wk(t); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, m / se if se > 0 else np.nan, len(x)


def events(with_trades):
    import pickle
    from common import K, trade  # noqa: E402
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    rows = []
    for p in sorted(glob.glob("s256/alpha/*.json")):
        fs = os.path.basename(p)[:-5]
        A = json.load(open(p))
        if fs not in K or not len(PU.get(fs, [])) or not A["k"]:
            continue
        av = {int(x[0]) // 1000 + 3600: float(x[2]) for x in A["k"]}            # конец часа → оборот Alpha
        spot0 = A.get("spot0")
        a = K[fs]; Tend = a["t"].astype(np.int64) + 900
        H = ((Tend - 1) // 3600 + 1) * 3600
        perp = pd.Series(a["qv"].astype(float)).groupby(H).sum()
        last = -1e18
        for j in PU[fs]:
            Tp = int(a["t"][j]) + 900
            if Tp < T0 or Tp >= T1 or Tp - last < 48 * 3600:
                continue
            if spot0 and Tp >= spot0:                                          # спот Binance уже был
                continue
            Hh = (Tp // 3600) * 3600
            v = av.get(Hh); pv = float(perp.get(Hh, np.nan))
            if v is None or pv != pv:
                continue                                                       # рынка Alpha в тот час не было
            share = v / max(v + pv, 1.0)
            hh = np.arange(Hh - 7 * DAY, Hh, 3600)                             # обычная доля монеты за 7 сут до пампа
            sh7 = [av[h] / max(av[h] + float(perp.get(h, np.nan)), 1.0) for h in hh if h in av and h in perp.index]
            base7 = float(np.median(sh7)) if len(sh7) >= 72 else np.nan
            r = dict(s=fs, t=Tp, share=share, base7=base7, mul=A.get("mulPoint"), chain=A.get("chain"))
            if with_trades:
                x = trade(fs, j, **EX)
                if x is None:
                    continue
                pl = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(fs, j - dd * 96, **EX))]
                r.update(net=x["net"], why=x["why"], pl=np.mean(pl) if pl else np.nan)
            last = Tp
            rows.append(r)
    return pd.DataFrame(rows)


def count():
    X = events(False)
    mo = (T1 - X.t.min()) / (30.44 * DAY)
    print("первое событие:", pd.Timestamp(X.t.min(), unit="s").date())
    print(f"пампов у перпов без спота при живом рынке Alpha: {len(X)} ({len(X) / mo:.1f} в месяц), монет {X.s.nunique()}")
    print("по кварталам:", pd.to_datetime(X.t, unit="s").dt.to_period("Q").value_counts().sort_index().to_dict())
    print("доля Alpha — квантили:", X.share.quantile([.1, .25, .5, .75, .9]).round(3).to_dict())
    hi = X[X.share >= SH]
    print(f"доля ≥ {SH:.0%}: {len(hi)} ({len(hi) / mo:.1f} в месяц); по месяцам 2026 г.:",
          pd.to_datetime(hi.t, unit="s").dt.strftime("%Y-%m").value_counts().sort_index().to_dict())


def line(x, mid, mo):
    if len(x) < 5:
        return f"n={len(x)}"
    m, t, n = ct(x.net, x.t); md, td, _ = ct(x.net - x.pl, x.t)
    return (f"n={n} ({n / mo:.1f} в месяц), {m:+.2%} (t по неделям {t:+.1f}); половины {x[x.t < mid].net.mean():+.2%} / "
            f"{x[x.t >= mid].net.mean():+.2%}; сверх плацебо {md:+.2%} (t {td:+.1f}), плацебо у {x.pl.notna().mean():.0%}; "
            f"стопов {(x.why == 'стоп').mean():.0%}")


def main():
    X = events(True)
    X.to_pickle("s256_trades.pkl")
    mid = float(X.t.median())                                          # половины — по числу пампов (рынок Alpha с 2025 г.)
    mo = (T1 - X.t.min()) / (30.44 * DAY)                              # частота — от первого события
    q = float(X[X.t < mid].share.quantile(2 / 3))                      # граница верхней трети — по первой половине (как s49)
    print(f"первое событие {pd.Timestamp(X.t.min(), unit='s').date()}, середина: {pd.Timestamp(mid, unit='s').date()}, "
          f"граница верхней трети доли Alpha по первой половине: {q:.2%}")
    hi, lo = X[X.share >= q], X[X.share < q]
    B = X[X.t >= mid]
    hb, lb = B[B.share >= q], B[B.share < q]
    print(f"\nПроверка — вторая половина, доля ≥ границы: {line(hb, mid, mo / 2)}")
    print(f"  вторая половина, доля < границы: {line(lb, mid, mo / 2)}")
    print(f"\nВесь период, доля ≥ границы: {line(hi, mid, mo)}")
    print(f"  весь период, доля < границы: {line(lo, mid, mo)}")
    q1 = float(X[X.t < mid].share.quantile(1 / 3))
    print(f"  нижняя треть (< {q1:.2%}): {line(X[X.share < q1], mid, mo)}")
    print(f"  средняя треть: {line(X[(X.share >= q1) & (X.share < q)], mid, mo)}")
    print(f"  все пампы перпов без спота: {line(X, mid, mo)}")
    ex = X.share / X.base7
    print(f"  доля в 2 раза выше обычной за 7 сут: {line(X[ex >= 2], mid, mo)}")
    print(f"  доля не выше обычной: {line(X[ex < 2], mid, mo)}")
    print(f"  доля ≥ 26% (порог 🛒): {line(X[X.share >= SH], mid, mo)}")
    print(f"  верхняя треть, повышенные очки Alpha (снимок mulPoint > 1): {line(hi[hi.mul.fillna(1) > 1], mid, mo)}")
    print(f"  верхняя треть, без повышенных очков: {line(hi[hi.mul.fillna(1) <= 1], mid, mo)}")
    m, t, n = ct(hb.net, hb.t); md = (hb.net - hb.pl).mean()
    print("\nпорог s256 (вторая половина): " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
          (("среднее > 0 и t ≥ 2 по неделям", m > 0 and t >= 2), ("сверх плацебо > 0", md > 0),
           ("лучше доли < границы", m > lb.net.mean()))))
    m, t, n = ct(hi.net, hi.t); md = (hi.net - hi.pl).mean()
    h1, h2 = hi[hi.t < mid].net.mean(), hi[hi.t >= mid].net.mean()
    print("правило владельца (весь период): " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
          (("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0), ("сверх плацебо > 0", md > 0))))


if __name__ == "__main__":
    {"count": count, "main": main}[sys.argv[1] if len(sys.argv) > 1 else "count"]()
