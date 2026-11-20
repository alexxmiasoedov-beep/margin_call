"""s235 — вето «BTC за сутки до входа ≤ −2%» на бэктестах журналов шорта пампов (метод — ВЫВОДЫ.md, записан до расчёта).
Журналы: 🛒 и пампы с долей Кореи ≥ 20% (s49), 🔝 (s65), 👀 (s83), ⏰ на трёх периодах (s88). Исход — шорт 10/25/48.
Запуск из /home/user/mc_data: python3 <repo>/research/s235/run.py"""
import os
import pickle

import numpy as np
import pandas as pd

WEEK, DAY = 7 * 86400, 86400
KF = {"2020–2022": "s117/k_2020.pkl", "2022–2024": "s117/k_oos.pkl", "2024–2026": "s2/k2y.pkl"}


def btc_series(per):
    p = f"s235/btc_{per}.npy"
    if not os.path.exists(p):
        os.makedirs("s235", exist_ok=True)
        K = pickle.load(open(KF[per], "rb")); B = K["BTC"]
        np.save(p, np.c_[B["t"].astype(np.int64) + 900, B["c"].astype(float)])
        del K
    return np.load(p)


def btc24(t, per):
    a = btc_series(per); bt, bc = a[:, 0], a[:, 1]
    t = np.asarray(t, np.int64)
    i = np.searchsorted(bt, t, "right") - 1; j = np.searchsorted(bt, t - DAY, "right") - 1
    ok = (i >= 0) & (j >= 0) & (bt[np.maximum(i, 0)] >= t - 1800)
    return np.where(ok, bc[np.maximum(i, 0)] / bc[np.maximum(j, 0)] - 1, np.nan)


def diff(y, g, t):
    """Разность средних (g − не g) и t с кластерами по неделям."""
    y = np.asarray(y, float); g = np.asarray(g, float); t = np.asarray(t, float)
    ok = np.isfinite(y) & np.isfinite(g); y, g, t = y[ok], g[ok], t[ok]
    if g.sum() < 3 or (1 - g).sum() < 3:
        return np.nan, np.nan
    X = np.c_[np.ones_like(g), g]; b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b
    w = (t // WEEK).astype(np.int64); XtX = np.linalg.inv(X.T @ X)
    S = sum(np.outer(v, v) for v in pd.DataFrame(X * e[:, None]).groupby(w).sum().to_numpy())
    se = np.sqrt(np.diag(XtX @ S @ XtX))
    return b[1], b[1] / se[1]


def sets():
    out = []
    E = pd.read_pickle("s49/trades.pkl")
    out.append(("🛒 (спот ≥ 26%)", "2024–2026", E[E.share >= 0.26], "net"))
    out.append(("пампы, Корея ≥ 20%", "2024–2026", E[E.kr >= 0.20], "net"))
    out.append(("🔝", "2024–2026", pd.read_pickle("s65/trades.pkl"), "S_10_25"))
    out.append(("👀", "2024–2026", pd.read_pickle("s83/trades.pkl"), "S_10_25"))
    for per, f in (("2024–2026", "s88/trades.pkl"), ("2022–2024", "s88/oos_trades.pkl"), ("2020–2022", "s88/oos2020_trades.pkl")):
        X = pd.read_pickle(f)
        X = X[X.open9.astype(bool) & (X.r1 >= 0.05) & (X.share >= 0.20)]
        out.append(("⏰", per, X, "S_10_25"))
    return out


def main():
    rows, pool = [], []
    for name, per, X, col in sets():
        X = X[X[col].notna()].copy()
        X["b24"] = btc24(X.t.to_numpy(), per)
        X = X[X.b24.notna()]
        veto = (X.b24 <= -0.02).astype(float)
        keep = 1 - veto
        d, td = diff(X[col], keep, X.t)
        rows.append({"журнал": name, "период": per, "сделок": len(X), "под вето": int(veto.sum()),
                     "все": X[col].mean(), "без вето": X[col][keep == 1].mean(), "под вето, доход": X[col][veto == 1].mean(),
                     "разность": d, "t": td})
        pool.append(pd.DataFrame({"y": X[col].to_numpy(), "keep": keep.to_numpy(), "t": X.t.to_numpy(),
                                  "grp": f"{name} {per}"}))
    R = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(R.to_string(formatters={c: "{:+.2%}".format for c in ("все", "без вето", "под вето, доход", "разность")} |
                      {"t": "{:+.1f}".format}))
    P = pd.concat(pool, ignore_index=True)
    # общая разность: МНК y ~ группа (свои средние) + keep, кластеры по неделям
    G = pd.get_dummies(P.grp).to_numpy(float)
    X = np.c_[G, P.keep.to_numpy()]; y = P.y.to_numpy(); b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b
    w = (P.t.to_numpy() // WEEK).astype(np.int64); XtX = np.linalg.pinv(X.T @ X)
    S = sum(np.outer(v, v) for v in pd.DataFrame(X * e[:, None]).groupby(w).sum().to_numpy())
    se = np.sqrt(np.diag(XtX @ S @ XtX))
    print(f"\nвсе журналы вместе (свои средние у каждого): без вето лучше на {b[-1]:+.2%} (t {b[-1] / se[-1]:+.1f}), "
          f"сделок {len(P)}, под вето {int((1 - P.keep).sum())}")
    ok_each = bool((R["разность"] > 0).all())
    ok = ok_each and b[-1] / se[-1] >= 2 and bool((R["без вето"] >= R["все"]).all())
    print("порог: разность > 0 везде — " + ("да" if ok_each else "нет") + f"; вместе t ≥ 2 — {'да' if b[-1] / se[-1] >= 2 else 'нет'}"
          + ("  → ПРОЙДЕН" if ok else "  → не пройден"))
    R.to_pickle("s235/result.pkl")


if __name__ == "__main__":
    main()
