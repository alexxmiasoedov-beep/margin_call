"""s89 — доля китайских бирж в пампе: оборот спота OKX + Bitget за последний полный час до закрытия свечи пампа к нему же
плюс оборот фьючерса Binance за тот же час. Шорт на закрытии свечи пампа: тейк 10 / стоп 25 / 48 ч (основной) и 7 сут
со стопом 50%. Основная группа — пампы без входов 🇰🇷 и 🛒 за сутки и 🔝 и 👀 за 7 сут; порог доли — по распределению
в основной группе (верхняя треть; для отчёта — выше медианы и верхняя десятая); плацебо — та же монета за 45/90/135 сут.
Гипотеза — ВЫВОДЫ.md, записана до расчёта. Запуск из папки с данными (после cn_fetch.py): python3 <путь>/s89/cn_test.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

H1 = 3600
EXITS = {"S_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "S_7d": dict(tp=None, sl=0.50, hold_h=168)}


def overlap_sets():
    S65 = pd.read_pickle("s65/trades.pkl"); S83 = pd.read_pickle("s83/trades.pkl")
    S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    wk, dy = {}, {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S83.s, S83.t)):
        wk.setdefault(s, []).append(t)
    for s, t in list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        dy.setdefault(s, []).append(t)
    return {s: np.array(v) for s, v in wk.items()}, {s: np.array(v) for s, v in dy.items()}


def line(lab, x0, col, months):
    x = x0[x0[col].notna()]
    if len(x) < 8:
        print(f"  {lab:34s} {col:7s} n={len(x)}")
        return
    m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
    h1, h2 = x[x.t < CUT], x[x.t >= CUT]
    (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
    print(f"  {lab:34s} {col:7s} n={n:5d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
          f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
          f" разница {dp:+6.2%} (t {tp:+4.1f})")


def main():
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    V = pickle.load(open("s89/cn_vol.pkl", "rb"))
    wk, dy = overlap_sets()
    rows, miss = [], 0
    for s, js in PU.items():
        a = K[s]; t = a["t"]; qv = a["qv"].astype(float)
        for j in js:
            v = V.get((s, int(j)))
            if v is None or None in v.values():
                miss += 1
                continue
            T = int(t[j]) + 900; he = T // H1 * H1; hs = he - H1
            b = float(qv[np.searchsorted(t, hs):np.searchsorted(t, he)].sum())
            cn = v["okx"] + v["bitget"]
            w, d = wk.get(s, np.zeros(0)), dy.get(s, np.zeros(0))
            r = dict(s=s, t=T, share=cn / max(cn + b, 1.0), okx=v["okx"], bitget=v["bitget"],
                     ov=bool(((w <= T) & (w >= T - 7 * DAY)).any() or ((d <= T) & (d >= T - DAY)).any()))
            for nm, kw in EXITS.items():
                y = trade(s, int(j), **kw)
                r[nm] = y["net"] if y else np.nan
                p = [z["net"] for dd in (45, 90, 135) if (k := idx_at(s, T - dd * DAY)) is not None and (z := trade(s, k, **kw))]
                r["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(r)
    X = pd.DataFrame(rows)
    X.to_pickle("s89/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    M = X[~X.ov]
    q = M.share.quantile([0.5, 2 / 3, 0.9])
    print(f"Пампов {len(X)} (без ответа бирж {miss}); основная группа без журналов {len(M)} ({len(M) / months:.1f} в месяц);"
          f" с нулевой долей {(M.share == 0).mean():.0%}")
    print("Доля Китая в основной группе: " + ", ".join(f"{k:.0%} — {v:.1%}" for k, v in M.share.quantile([0.25, 0.5, 2 / 3, 0.9]).items()))
    for col in EXITS:
        print(f"\n{col}")
        line(f"верхняя треть (≥ {q[2 / 3]:.1%}, основная)", M[M.share >= q[2 / 3]], col, months)
        line(f"выше медианы (≥ {q[0.5]:.1%})", M[M.share >= q[0.5]], col, months)
        line(f"верхняя десятая (≥ {q[0.9]:.1%})", M[M.share >= q[0.9]], col, months)
        line("ниже медианы (сравнение)", M[M.share < q[0.5]], col, months)
        line("все пампы основной группы", M, col, months)


if __name__ == "__main__":
    main()
