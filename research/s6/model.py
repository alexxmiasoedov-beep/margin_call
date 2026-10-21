"""Скользящее обучение: для каждого месяца модель учится только на пампах, чьи сделки уже закрылись до начала месяца,
и предсказывает вероятность «тейк раньше стопа» для пампов этого месяца. Итог — винрейт и доход по порогам вероятности,
против безубыточного винрейта стоп/(тейк+стоп) и простых правил."""
import sys, datetime, warnings
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
warnings.filterwarnings("ignore")
D = pd.read_pickle("s6/feat.pkl").sort_values("t").reset_index(drop=True)
OUT = [c for c in D.columns if c.startswith(("S_", "L_")) or c in ("mfe_s24", "mae_s24", "mfe_s48", "mae_s48", "ret48", "ret24", "ret4", "full")]
X_COLS = [c for c in D.columns if c not in OUT + ["s", "t", "i", "y"]]
D["mon"] = pd.to_datetime(D.t, unit="s").dt.to_period("M")
months = sorted(D.mon.unique())
def walk(target, start=6, **kw):
    p = np.full(len(D), np.nan)
    for m in months[start:]:
        m0 = m.start_time.tz_localize("UTC").timestamp()
        tr = D[(D.t + 48 * 3600 < m0) & D[target].notna()]; te = D.mon == m
        if tr[target].nunique() < 2 or not te.any(): continue
        clf = HistGradientBoostingClassifier(max_depth=kw.get("depth", 3), learning_rate=0.05, max_iter=kw.get("iters", 250),
                                             min_samples_leaf=kw.get("leaf", 40), l2_regularization=1.0, random_state=0)
        clf.fit(tr[X_COLS], (tr[target] > 0).astype(int)); p[te.values] = clf.predict_proba(D.loc[te, X_COLS])[:, 1]
    return p
def report(col, p, label):
    tp, sl = (int(x) for x in col.split("_")[1:]); be = sl / (tp + sl)
    E = D[~np.isnan(p)].assign(p=p[~np.isnan(p)]); E["q"] = pd.to_datetime(E.t, unit="s").dt.to_period("Q")
    print(f"\n=== {label} {col}: тейк {tp}% / стоп {sl}%, безубыточный винрейт {be:.1%}; проверка на {len(E)} пампах ({E.mon.min()}–{E.mon.max()})")
    print(f"   все пампы: винрейт {(E[col] > 0).mean():.1%}, {E[col].mean() * 100:+.2f}% на сделку")
    for top in (0.5, 0.3, 0.2, 0.1, 0.05, 0.02):
        thr = E.p.quantile(1 - top); g = E[E.p >= thr]; qm = g.groupby("q")[col].mean()
        y1 = g[g.y == 1]; y2 = g[g.y == 2]
        print(f"   верхние {top:4.0%} (p ≥ {thr:.2f}): {len(g):5d} сделок | винрейт {(g[col] > 0).mean():.1%} | {g[col].mean() * 100:+.2f}% на сделку "
              f"| 1-й год {(y1[col] > 0).mean():.1%} / {y1[col].mean() * 100:+.2f}% ({len(y1)}) | 2-й {(y2[col] > 0).mean():.1%} / {y2[col].mean() * 100:+.2f}% ({len(y2)}) "
              f"| кварталов в плюсе {(qm > 0).sum()}/{len(qm)}")
    return E
if __name__ == "__main__":
    cols = sys.argv[1:] or ["S_10_25", "S_7_20", "S_5_15", "S_10_15", "S_15_25", "L_30_15", "L_20_10", "L_10_10", "L_5_10"]
    for col in cols:
        p = walk(col); E = report(col, p, "ШОРТ" if col.startswith("S") else "ЛОНГ")
        D[f"p_{col}"] = p
    D[[c for c in D.columns if c.startswith("p_")] + ["s", "t"]].to_pickle("s6/preds.pkl")
