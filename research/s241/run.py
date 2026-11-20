"""s241 — OI в монетах во время пампа как фильтр шорта пампов (метод — ВЫВОДЫ.md, записан до расчёта).
Пампы s159 (шорт 10/25/48, net), dOI3 = OI(строка ≤ T − 1 ч) / OI(строка ≤ T − 4 ч) − 1; трети внутри периода.
Запуск из /home/user/mc_data (после s230/fetch_metrics.py): python3 <repo>/research/s241/run.py"""
import os

import numpy as np
import pandas as pd

WEEK, H = 7 * 86400, 3600
PERS = ("2022–2024", "2024–2026")


def oi_series(s, per):
    """(время, OI в монетах) по часам."""
    if per == "2022–2024":
        p = f"s230/metrics/{s}.npy"
        if not os.path.exists(p):
            return None
        a = np.load(p)
        return (a[:, 0].astype(np.int64), a[:, 1].astype(float)) if len(a) else None
    p = f"s228/met/{s}.npz"
    if not os.path.exists(p):
        return None
    z = np.load(p)
    return (z["t"].astype(np.int64), z["v"][:, 0].astype(float)) if len(z["t"]) else None


def doi3(E, per):
    out = np.full(len(E), np.nan)
    cache = {}
    for i, (s, t) in enumerate(zip(E.s, E.t.astype(np.int64))):
        if s not in cache:
            cache[s] = oi_series(s, per)
        a = cache[s]
        if a is None:
            continue
        tt, oi = a
        j1 = np.searchsorted(tt, t - H, "right") - 1; j4 = np.searchsorted(tt, t - 4 * H, "right") - 1
        if j1 >= 0 and j4 >= 0 and j1 > j4 and tt[j1] >= t - 2 * H and oi[j4] > 0 and np.isfinite(oi[j1]):
            out[i] = oi[j1] / oi[j4] - 1
    return out


def diff_fe(y, g, t, grp):
    """Разность средних (g = 1 против g = 0) со своими средними по группам; t с кластерами по неделям."""
    y = np.asarray(y, float); g = np.asarray(g, float); t = np.asarray(t, float)
    G = pd.get_dummies(pd.Series(grp)).to_numpy(float)
    X = np.c_[G, g]; b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b
    w = (t // WEEK).astype(np.int64); XtX = np.linalg.pinv(X.T @ X)
    S = sum(np.outer(v, v) for v in pd.DataFrame(X * e[:, None]).groupby(w).sum().to_numpy())
    se = np.sqrt(np.diag(XtX @ S @ XtX))
    return b[-1], b[-1] / se[-1]


def main():
    parts = []
    for per in PERS:
        E = pd.read_pickle(f"s159_{per}.pkl").copy()
        E["d"] = doi3(E, per); E["per"] = per
        E = E[E.d.notna() & E.net.notna()]
        q1, q2 = E.d.quantile([1 / 3, 2 / 3])
        E["tri"] = np.where(E.d <= q1, "низ", np.where(E.d >= q2, "верх", "середина"))
        parts.append(E)
        print(f"{per}: пампов с OI {len(E)}; трети dOI3: ≤ {q1:+.1%} | ≥ {q2:+.1%}")
        for sub, X in (("все пампы", E), ("спот ≥ 26%", E[E.share >= 0.26])):
            line = []
            for tr in ("низ", "середина", "верх"):
                y = X.net[X.tri == tr]
                line.append(f"{tr} {y.mean():+.2%} (n {len(y)}, стопов {(y <= -0.24).mean():.0%})")
            print(f"  {sub}: " + "; ".join(line))
    A = pd.concat(parts, ignore_index=True)
    B = A[A.tri.isin(["низ", "верх"])]
    res = {}
    for per in PERS:
        X = B[B.per == per]
        res[per] = X.net[X.tri == "верх"].mean() - X.net[X.tri == "низ"].mean()
    d, td = diff_fe(B.net, (B.tri == "верх").astype(float), B.t, B.per)
    ok = all(v > 0 for v in res.values()) and td >= 2
    print("верх − низ по периодам: " + ", ".join(f"{k} {v:+.2%}" for k, v in res.items())
          + f"; вместе {d:+.2%} (t {td:+.1f}) → " + ("ПРОЙДЕНО" if ok else "не пройдено"))
    S = B[B.share >= 0.26]
    if len(S) > 20:
        d2, t2 = diff_fe(S.net, (S.tri == "верх").astype(float), S.t, S.per)
        print(f"спот ≥ 26%: верх − низ {d2:+.2%} (t {t2:+.1f}), пампов {len(S)}")
    A.to_pickle("s241_pumps.pkl")


if __name__ == "__main__":
    main()
