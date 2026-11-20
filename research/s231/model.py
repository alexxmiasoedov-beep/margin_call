"""s231 — модель LightGBM на признаках s225 вместо комитета 🗳 (метод — ВЫВОДЫ.md, записан до расчёта).
Обучение на A, ранняя остановка по ошибке на B, порог прогноза — квантиль B (верхние 2/5/10/20%) по наибольшему t честных
сделок на B; то же абсолютное значение прогноза — на C и D. Сделки, плацебо и контроль из перемешанных исходов — как
в s223/committee.py, свежий отрезок D — как в s224/d_check.py.
Запуск из /home/user/mc_data: python3 <repo>/research/s231/model.py"""
import os
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s216", "s223", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
os.environ.setdefault("PFX", "s225")
import bombe  # noqa: E402
import committee as CM  # noqa: E402

DAY = 86400
COL = "y_hs4"
D0 = pd.Timestamp("2026-10-22", tz="UTC").timestamp()
QS = (0.02, 0.05, 0.10, 0.20)
SEEDS = (1, 2, 3, 4, 5)
PAR = dict(objective="regression", num_leaves=15, min_data_in_leaf=300, learning_rate=0.02, feature_fraction=0.7,
           bagging_fraction=0.7, bagging_freq=1, lambda_l2=10.0, verbose=-1, num_threads=4)


def fit_predict(X, y, seg, Xs):
    """Пять моделей на A с ранней остановкой по B; хвосты исхода обрезаны по 1-му и 99-му процентилю A. → прогнозы для
    каждого набора Xs (среднее моделей), число деревьев, важность признаков (gain, среднее)."""
    a, b = seg == 0, seg == 1
    lo, hi = np.nanpercentile(y[a], [1, 99]); yc = np.clip(y, lo, hi)
    out = [np.zeros(len(x)) for x in Xs]; trees, imp = [], 0.0
    for sd in SEEDS:
        m = lgb.train({**PAR, "seed": sd}, lgb.Dataset(X[a], yc[a]), num_boost_round=3000,
                      valid_sets=[lgb.Dataset(X[b], yc[b])], callbacks=[lgb.early_stopping(200, verbose=False)])
        it = m.best_iteration or m.current_iteration()
        trees.append(it); imp = imp + m.feature_importance("gain", iteration=it) / len(SEEDS)
        for j, x in enumerate(Xs):
            out[j] += m.predict(x, num_iteration=it) / len(SEEDS)
    return out, trees, imp


def pick_q(p, seg, D, y, end, T):
    """Квантиль прогнозов B с наибольшим t честных сделок на B (≥ 30 сделок). → (доля, t, доход, n, порог)."""
    best = None
    for q in QS:
        thr = float(np.quantile(p[seg == 1], 1 - q))
        tk = CM.honest((p >= thr) & (seg == 1), D, y, end)
        m, t, n = CM.ct(y[tk], T[tk])
        if n >= 30 and np.isfinite(t) and (best is None or t > best[1]):
            best = (q, t, m, n, thr)
    return best


def main():
    F = pd.read_pickle("s225_feat.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    D = F[F[COL].notna()].reset_index(drop=True)
    FE = [c for c in D.columns if c not in bombe.OUTC | {"s", "T"} and not c.startswith(("y_", "u_"))
          and pd.api.types.is_numeric_dtype(D[c])]
    T = D["T"].to_numpy(np.int64); seg = np.where(T < bombe.TA, 0, np.where(T < bombe.TB, 1, 2))
    y = D[COL].to_numpy(float); end = D["u_e_" + COL[2:]].to_numpy(float)
    X = D[FE].to_numpy(np.float32)
    FD = pd.read_pickle("s224/feat_D_s225.pkl")
    XD = FD[FD[COL].notna() & (FD["T"] >= D0) & (FD["T"] % (4 * 3600) == 0)].sort_values(["T", "s"]).reset_index(drop=True)
    miss = [c for c in FE if c not in XD.columns]
    assert not miss, f"в файле D нет признаков {miss}"
    TD = XD["T"].to_numpy(np.int64); yD = XD[COL].to_numpy(float); eD = XD["u_e_" + COL[2:]].to_numpy(float)
    print(f"признаков {len(FE)}; наблюдений A/B/C {np.bincount(seg).tolist()}, D {len(XD)}")

    (p, pD), trees, imp = fit_predict(X, y, seg, [X, XD[FE].to_numpy(np.float32)])
    print(f"деревьев по зёрнам: {trees}")
    top = sorted(zip(imp, FE), reverse=True)[:12]
    print("важность (gain): " + ", ".join(f"{f} {g / imp.sum():.0%}" for g, f in top))
    for s_, nm in ((0, "A"), (1, "B"), (2, "C")):
        ic = pd.Series(p[seg == s_]).corr(pd.Series(y[seg == s_]), method="spearman")
        print(f"  ранговая корреляция прогноза и исхода на {nm}: {ic:+.3f}")
    b = pick_q(p, seg, D, y, end, T)
    print("на B: " + "; ".join(
        f"верхние {q:.0%}: " + "{:+.2%} (t {:+.1f}, n {})".format(*CM.ct(y[tk], T[tk])) for q in QS
        for tk in [CM.honest((p >= np.quantile(p[seg == 1], 1 - q)) & (seg == 1), D, y, end)]))
    q, _, _, _, thr = b
    print(f"выбрано на B: верхние {q:.0%}, порог прогноза {thr:+.5f}")

    months = (CM.C1 - bombe.TB) / (30.44 * DAY)
    tk = CM.honest((p >= thr) & (seg == 2), D, y, end)
    m, t, n = CM.ct(y[tk], T[tk])
    h1, h2 = y[tk][T[tk] < CM.MIDC].mean(), y[tk][T[tk] >= CM.MIDC].mean()
    pl = CM.placebo(D, tk, COL); md, td, _ = CM.ct(y[tk] - pl, T[tk])
    print(f"C: {n} сделок ({n / months:.1f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
          f"сверх плацебо {md:+.2%} (t {td:+.1f})")
    ctl = []
    for sd in (0, 1, 2):
        ys = CM.shuffled_y(D, y, sd)
        (ps,), _, _ = fit_predict(X, ys, seg, [X])
        bs = pick_q(ps, seg, D, ys, end, T)
        if not bs:
            ctl.append(np.nan); continue
        ts = CM.honest((ps >= bs[4]) & (seg == 2), D, y, end)
        ctl.append(CM.ct(y[ts], T[ts])[0])
        print(f"  контроль {sd}: верхние {bs[0]:.0%}, C {ctl[-1]:+.2%} (n {len(ts)})")
    okC = [("t ≥ 3", m > 0 and t >= 3), ("≥ 20 в мес.", n / months >= 20), ("половины > 0", h1 > 0 and h2 > 0),
           ("сверх плацебо > 0", md > 0), ("лучше контроля", m > np.nanmean(ctl))]
    print("порог C: " + "; ".join(f"{a} — {'да' if c else 'нет'}" for a, c in okC)
          + ("  → ПРОЙДЕН" if all(c for _, c in okC) else "  → не пройден"))

    tkD = CM.honest(pD >= thr, XD, yD, eD)
    plD = CM.placebo(XD, tkD, COL)
    mD, tD, nD = CM.ct(yD[tkD], TD[tkD])
    monD = (TD.max() + 3600 - D0) / (30.44 * DAY)
    yy = np.r_[y[tk], yD[tkD]]; tt = np.r_[T[tk], TD[tkD]]; pp = np.r_[pl, plD]
    m2, t2, n2 = CM.ct(yy, tt); md2, td2, _ = CM.ct(yy - pp, tt)
    print(f"D: {nD} сделок ({nD / monD:.1f} в мес.), {mD:+.2%} (t {tD:+.1f}); сверх плацебо "
          f"{CM.ct(yD[tkD] - plD, TD[tkD])[0]:+.2%}; все наблюдения D {np.nanmean(yD):+.2%}")
    print(f"C + D: {n2} сделок ({n2 / (months + monD):.1f} в мес.), {m2:+.2%} (t {t2:+.1f}); сверх плацебо {md2:+.2%} "
          f"(t {td2:+.1f})")
    okD = [("D > 0", mD > 0), ("C + D: t ≥ 3", m2 > 0 and t2 >= 3), ("≥ 20 в мес.", n2 / (months + monD) >= 20),
           ("лучше плацебо", md2 > 0)]
    print("порог D: " + "; ".join(f"{a} — {'да' if c else 'нет'}" for a, c in okD)
          + ("  → ПРОЙДЕН" if all(c for _, c in okD) else "  → не пройден"))

    # сравнение с комитетом 🗳 на тех же отрезках
    cC = pd.read_pickle("s225_comm_y_hs4.pkl"); cD = pd.read_pickle("s224_D_s225_y_hs4.pkl")
    cm = pd.concat([cC, cD]); mc, tc, nc = CM.ct(cm.y.to_numpy(), cm["T"].to_numpy())
    mine = set(zip(D.s.values[tk], T[tk])) | set(zip(XD.s.values[tkD], TD[tkD]))
    theirs = set(zip(cm.s, cm["T"]))
    both = mine & theirs
    yb = [v for (s_, t_), v in zip(zip(np.r_[D.s.values[tk], XD.s.values[tkD]], tt), yy) if (s_, t_) in both]
    yo = [v for (s_, t_), v in zip(zip(np.r_[D.s.values[tk], XD.s.values[tkD]], tt), yy) if (s_, t_) not in both]
    print(f"комитет 🗳 на C + D: {nc} сделок, {mc:+.2%} (t {tc:+.1f}); общих сделок с моделью {len(both)} "
          f"({len(both) / max(len(mine), 1):.0%} сделок модели): у общих {np.mean(yb) if yb else np.nan:+.2%}, "
          f"у остальных сделок модели {np.mean(yo) if yo else np.nan:+.2%}")
    pd.DataFrame({"s": np.r_[D.s.values[tk], XD.s.values[tkD]], "T": tt, "y": yy, "pl": pp,
                  "p": np.r_[p[tk], pD[tkD]]}).to_pickle("s231_trades.pkl")


if __name__ == "__main__":
    main()
