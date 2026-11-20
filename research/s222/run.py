"""s222 — лонг при совпадении 🇹🇷 и 🇰🇷 на одной монете (вопрос владельца 20.11; гипотезы — ВЫВОДЫ.md, записаны до расчёта,
коммит 81d4f42).

- Пары — входы 🇹🇷 и 🇰🇷 из s102/trades.pkl: та же монета, входы не дальше 1 ч. Лонг входит на втором из двух входов.
- Шире — два разных журнала из 🇹🇷, 🇰🇷, 🛒 (s49/trades.pkl, доля спота ≥ 26%) по одной монете в пределах 1 ч; одно событие
  на монету за 48 ч.
- Сделки — s15/common.trade (side +1, комиссия, фандинг, стоп по худшей цене); хедж — индекс альтов s103 на фактический
  срок сделки (fastbt.alt_mv); плацебо — та же сделка той же монеты за 45/90/135 сут до входа; t — по неделям.
- Наблюдение после расчёта (не записано заранее): лонг на закрытии свечи, где 🇹🇷 выбило по стопу.

Запуск из /home/user/mc_data: python3 <repo>/research/s222/run.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
import fastbt as FB  # noqa: E402

DAY, WEEK, H = 86400, 7 * 86400, 3600
T0, T1 = pd.Timestamp("2024-10-19", tz="UTC").timestamp(), pd.Timestamp("2026-10-15", tz="UTC").timestamp()
MID = (T0 + T1) / 2
MONTHS = (T1 - T0) / (30.44 * DAY)
LONGS = {"Л1 тейк 25 / стоп 10 / 48 ч": (0.25, 0.10, 48), "Л2 4 ч, стоп 10": (None, 0.10, 4),
         "Л3 24 ч, стоп 15": (None, 0.15, 24), "Л4 48 ч, стоп 25": (None, 0.25, 48)}


def ct(x, t):
    """Среднее и t с кластерами по неделям входа."""
    x = np.asarray(x, float); w = (np.asarray(t, float) // WEEK).astype(np.int64); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return (x.mean() if len(x) else np.nan), np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def idx(s, te):
    """Свеча, на закрытии которой вход te."""
    t = K[s]["t"]; i = int(np.searchsorted(t, te - 900))
    return i if i < len(t) and t[i] == te - 900 and i >= 96 else None


def deal(s, i, tp, sl, h):
    r = trade(s, i, tp, sl, h, side=+1)
    if not r:
        return None
    t = K[s]["t"]; t0, t1 = float(t[i]) + 900, float(t[i + r["bars"]]) + 900
    mv = FB.alt_mv(np.array([t0]), np.array([t1]))[0]
    return r["net"], r["net"] - mv, r["why"]


def placebo(s, i, tp, sl, h):
    t = K[s]["t"]; v = []
    for d in (45, 90, 135):
        j = int(np.searchsorted(t, t[i] - d * DAY))
        if 96 <= j < len(t) and t[j] == t[i] - d * DAY:
            r = trade(s, j, tp, sl, h, side=+1)
            if r:
                v.append(r["net"])
    return float(np.mean(v)) if v else np.nan


def run(E, tp, sl, h):
    """E: DataFrame(s, te). Возвращает сделки лонга."""
    out = []
    for s, te in zip(E.s, E.te):
        if s not in K:
            continue
        i = idx(s, te)
        d = deal(s, i, tp, sl, h) if i is not None else None
        if d:
            out.append(dict(s=s, te=te, net=d[0], hed=d[1], why=d[2], pl=placebo(s, i, tp, sl, h)))
    return pd.DataFrame(out)


def line(R):
    if not len(R):
        return "сделок нет"
    m, t, n = ct(R.net, R.te); mh, th, _ = ct(R.hed, R.te); md, td, _ = ct(R.net - R.pl, R.te)
    h1, h2 = R[R.te < MID], R[R.te >= MID]
    return (f"n={n} ({n / MONTHS:.1f} в мес.) {m:+.2%} (t {t:+.1f}); половины {h1.net.mean():+.2%} / {h2.net.mean():+.2%}; "
            f"с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {(R.why == 'стоп').mean():.0%}, "
            f"тейков {(R.why == 'тейк').mean():.0%}")


def passed(R):
    m, t, _ = ct(R.net, R.te); md, _, _ = ct(R.net - R.pl, R.te)
    h1, h2 = R[R.te < MID].net.mean(), R[R.te >= MID].net.mean()
    return m > 0 and t >= 2 and h1 > 0 and h2 > 0 and md > 0


def main():
    X = pd.read_pickle("s102/trades.pkl")
    TR, KR = X[X.j == "🇹🇷"].reset_index(drop=True), X[X.j == "🇰🇷"].reset_index(drop=True)
    kr = {s: g for s, g in KR.groupby("s")}
    P = []
    for r in TR.itertuples():
        g = kr.get(r.s)
        if g is None:
            continue
        d = (g.t - r.t).abs()
        if (d <= H).any():
            b = g.loc[d.idxmin()]
            P.append(dict(s=r.s, tT=r.t, tK=b.t, te=max(r.t, b.t), r4=r.r4, sh=r.sh, whyT=r.why, whyK=b.why))
    P = pd.DataFrame(P).drop_duplicates(["s", "te"]).sort_values("te").reset_index(drop=True)
    P["dt"] = (P.tT - P.tK).abs()
    print(f"пар 🇹🇷 + 🇰🇷 (≤ 1 ч): {len(P)} ({len(P) / MONTHS:.1f} в мес.); в одной свече {int((P.dt == 0).sum())}, "
          f"≤ 15 мин {int((P.dt <= 900).sum())}")

    # шире: два разных журнала из 🇹🇷, 🇰🇷, 🛒 в пределах 1 ч, одно событие на монету за 48 ч
    sp = pd.read_pickle("s49/trades.pkl"); sp = sp[(sp.share >= 0.26) & (sp.t >= T0) & (sp.t <= T1)]
    A = pd.concat([TR[["s", "t"]].assign(j="🇹🇷"), KR[["s", "t"]].assign(j="🇰🇷"),
                   pd.DataFrame(dict(s=sp.s, t=sp.t.astype(float), j="🛒"))]).sort_values(["s", "t"])
    W = []
    for s, g in A.groupby("s"):
        last = -1e18; tt, jj = g.t.values, g.j.values
        for k in range(len(g)):
            prev = (tt[:k] >= tt[k] - H) & (jj[:k] != jj[k])
            if prev.any() and tt[k] - last >= 48 * H:
                W.append(dict(s=s, te=float(tt[k]), js="+".join(sorted(set(jj[:k][prev]) | {jj[k]}))))
                last = tt[k]
    W = pd.DataFrame(W)
    print(f"шире (два разных журнала из 🇹🇷, 🇰🇷, 🛒 за 1 ч): {len(W)} ({len(W) / MONTHS:.1f} в мес.); "
          + ", ".join(f"{k} {v}" for k, v in W.js.value_counts().items()))

    ok_any = []
    res = {}
    for name, (tp, sl, h) in LONGS.items():
        R = run(P, tp, sl, h).merge(P[["s", "te", "r4", "dt", "whyT"]], on=["s", "te"])
        res[name] = R
        print(f"\n=== {name} ===")
        print(f"  пары 🇹🇷 + 🇰🇷:      {line(R)}")
        print(f"  ≤ 15 мин:           {line(R[R.dt <= 900])}")
        print(f"  в одной свече:      {line(R[R.dt == 0])}")
        Rw = run(W, tp, sl, h)
        print(f"  шире (+🛒):          {line(Rw)}")
        for lab, m in (("памп 10–15%", R.r4 < 0.15), ("памп 15–25%", (R.r4 >= 0.15) & (R.r4 < 0.25)), ("памп ≥ 25%", R.r4 >= 0.25)):
            print(f"  {lab}:        {line(R[m])}")
        if passed(R):
            ok_any.append(name)
    print("\nпорог s222 (среднее > 0, t ≥ 2 по неделям, обе половины > 0, лучше плацебо) на парах:",
          ", ".join(ok_any) if ok_any else "не пройден ни одним вариантом")

    # для сравнения: те же лонги на остальных входах 🇹🇷 и 🇰🇷 (без пары)
    print("\nдля сравнения — те же лонги на входах без пары:")
    paired_T = set(zip(P.s, P.tT)); paired_K = set(zip(P.s, P.tK))
    for lab, D, pp in (("🇹🇷 без пары", TR, paired_T), ("🇰🇷 без пары", KR, paired_K)):
        E = D[[(s, t) not in pp for s, t in zip(D.s, D.t)]].rename(columns={"t": "te"})
        for name in ("Л3 24 ч, стоп 15", "Л4 48 ч, стоп 25"):
            print(f"  {lab}, {name}: {line(run(E, *LONGS[name]))}")

    # наблюдение (не записано заранее): лонг на закрытии свечи, где 🇹🇷 выбило по стопу
    print("\nнаблюдение — лонг с момента стопа 🇹🇷 (не записано заранее):")
    for lab, D in (("пары, 🇹🇷 по стопу", TR[[(s, t) in paired_T for s, t in zip(TR.s, TR.t)]]),
                   ("все 🇹🇷 по стопу", TR)):
        rows = []
        for s, t in zip(D.s, D.t):
            i = idx(s, t)
            r = trade(s, i, 0.10, 0.15, 24) if i is not None else None
            if r and r["why"] == "стоп":
                rows.append(dict(s=s, te=float(K[s]["t"][i + r["bars"]]) + 900))
        E = pd.DataFrame(rows)
        for name in ("Л2 4 ч, стоп 10", "Л3 24 ч, стоп 15", "Л4 48 ч, стоп 25"):
            print(f"  {lab}, {name}: {line(run(E, *LONGS[name]))}")
    pd.concat([R.assign(v=k) for k, R in res.items()]).to_pickle("s222_trades.pkl")


if __name__ == "__main__":
    main()
