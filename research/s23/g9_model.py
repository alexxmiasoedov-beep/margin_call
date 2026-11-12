"""Сборка слабых признаков в одну модель (поиск). Таблица s23/long4h.pkl (срезы раз в 4 ч). Признаки — ранги среди монет
среза; цель — ранг дохода к рынку через 72 ч (и 24 ч) на срезе. Режим dev: обучение на первой половине до CUT − 120 сут,
проверка на последних 117 сутках первой половины (зазор 3 сут). Модели: гребневая регрессия на рангах и LightGBM
(малая сложность). Метрики: средний IC Спирмена по срезам, децили, разница D10 − D1. Запуск из папки с данными:
python3 g9_model.py dev"""
import sys
import numpy as np, pandas as pd
import lightgbm as lgb
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT, nw_t

MODE = sys.argv[1] if len(sys.argv) > 1 else "dev"
FEATS = ["R", "R72", "R7d", "PHI", "D", "B", "A", "TS", "VC", "PMW", "dPM", "F8", "ETA3", "DH30", "DL30", "NPUMP", "AGE", "Vb", "lam"]
L = pd.read_pickle("s23/long4h.pkl")
L = L[L.Y72.notna() & L.Y24.notna()].copy()
g = L.groupby("T")
for f in FEATS:
    L["r_" + f] = g[f].rank(pct=True) - 0.5
for y in ("Y24", "Y72"):
    L["r_" + y] = g[y].rank(pct=True) - 0.5
X = ["r_" + f for f in FEATS]
L[X] = L[X].fillna(0.0)                         # нет признака — середина


def evaluate(d, pred, ycol, title):
    d = d.assign(p=pred)
    ic = d.groupby("T").apply(lambda q: q.p.rank().corr(q[ycol].rank()), include_groups=False)
    daily = ic.groupby(ic.index // 86400).mean()
    dec = d.groupby("T").apply(lambda q: q.assign(k=pd.qcut(q.p.rank(method="first"), 10, labels=False)).groupby("k")[ycol].mean(),
                               include_groups=False)
    sp = dec[9] - dec[0]
    lag = 3 if ycol == "Y72" else 1
    spd = sp.groupby(sp.index // 86400).mean()
    print(f"  {title}: IC {ic.mean() * 100:+.2f}% (t по дням {nw_t(daily, lag):+.1f}), децили {ycol}, %: "
          + " ".join(f"{v * 100:+.2f}" for v in dec.mean()) + f" | D10−D1 {sp.mean() * 100:+.2f}% (t {nw_t(spd, lag):+.1f})")
    return ic


if MODE == "dev":
    tr = L[L["T"] < CUT - 120 * 86400]
    va = L[(L["T"] >= CUT - 117 * 86400) & (L["T"] < CUT)]
    print(f"dev: обучение {tr['T'].nunique()} срезов ({len(tr)} строк), проверка {va['T'].nunique()} срезов ({len(va)} строк)")
    for ycol in ("Y72", "Y24"):
        yt = "r_" + ycol
        print(f"\n== цель {ycol}")
        # гребневая регрессия на рангах
        A = tr[X].values; b = tr[yt].values
        w = np.linalg.solve(A.T @ A + 1e3 * np.eye(len(X)), A.T @ b)
        print("  веса гребневой (×100): " + ", ".join(f"{f}={v * 100:+.1f}" for f, v in sorted(zip(FEATS, w), key=lambda z: -abs(z[1]))))
        evaluate(va, va[X].values @ w, ycol, "гребневая")
        for leaves, mdl in ((7, 5000), (15, 2000)):
            m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=leaves, min_child_samples=mdl, subsample=0.7,
                                  subsample_freq=1, colsample_bytree=0.8, reg_lambda=10, verbose=-1)
            m.fit(tr[X], tr[yt])
            evaluate(va, m.predict(va[X]), ycol, f"LightGBM {leaves} листьев")
        imp = pd.Series(m.booster_.feature_importance("gain"), index=FEATS).sort_values(ascending=False)
        print("  важность (gain, %): " + ", ".join(f"{k}={v / imp.sum() * 100:.0f}" for k, v in imp.items()))
        for f in FEATS:
            pass
