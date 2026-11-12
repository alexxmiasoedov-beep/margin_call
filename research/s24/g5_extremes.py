"""Поиск «карманов» доходности: LightGBM на доход к рынку за 72 ч (винсоризация 1%/99% по срезу), признаки — ранги 19
признаков s23 (s23/long4h.pkl). Обучение — первая половина (до CUT − 3 сут), проверка — вторая половина один раз:
средний доход к рынку у 1% и 2% крайних прогнозов (лонг верхних, шорт нижних), затем сделки по срезам 00:00 UTC через
common.trade (комиссия 0,1%, фандинг, стоп 25%, 72 ч). Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
import lightgbm as lgb
sys.path.insert(0, "/home/user/margin_call/research/s23")
from feat23 import CUT                                            # noqa: E402
from common23 import K, ct, trade                                # noqa: E402

FEATS = ["R", "R72", "R7d", "PHI", "D", "B", "A", "TS", "VC", "PMW", "dPM", "F8", "ETA3", "DH30", "DL30", "NPUMP", "AGE", "Vb", "lam"]
L = pd.read_pickle("s23/long4h.pkl")
L = L[L.Y72.notna()].copy()
g = L.groupby("T")
for f in FEATS:
    L["r_" + f] = g[f].rank(pct=True) - 0.5
lo = g.Y72.transform(lambda y: y.quantile(0.01)); hi = g.Y72.transform(lambda y: y.quantile(0.99))
L["yw"] = L.Y72.clip(lo, hi)
X = ["r_" + f for f in FEATS]
L[X] = L[X].fillna(0.0)
tr = L[L["T"] < CUT - 3 * 86400]; te = L[L["T"] >= CUT].copy()
m = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=3000, subsample=0.7, subsample_freq=1,
                      colsample_bytree=0.8, reg_lambda=10, verbose=-1).fit(tr[X], tr["yw"])
te["p"] = m.predict(te[X])
imp = pd.Series(m.booster_.feature_importance("gain"), index=FEATS).sort_values(ascending=False)
print("важность (gain, %): " + ", ".join(f"{k}={v / imp.sum() * 100:.0f}" for k, v in imp.head(10).items()))
te["q"] = te.groupby("T").p.rank(pct=True)
for lab, sel, side in (("верхний 1% прогноза (лонг)", te.q >= 0.99, 1), ("верхний 2%", te.q >= 0.98, 1),
                       ("нижний 1% (шорт)", te.q <= 0.01, -1), ("нижний 2%", te.q <= 0.02, -1), ("середина 40–60%", (te.q > 0.4) & (te.q < 0.6), 1)):
    x = side * te.Y72[sel]; mm, t, n = ct(x.values, te["T"][sel].values)
    print(f"  вторая половина, {lab:>28}: n={n:6d}, доход стороны к рынку за 72 ч {mm * 100:+.2f}% (t {t:+.1f}), медиана {x.median() * 100:+.2f}%")
# сделки: срезы 00:00, крайние 2%
d = te[te["T"] % 86400 == 0]


def bar(s, T):
    t = K[s]["t"]; i = int(np.searchsorted(t, T - 900))
    return i if i < len(t) and t[i] + 900 == T else None


res = []
for T, q in d.groupby("T"):
    for side, sel in ((1, q[q.q >= 0.98]), (-1, q[q.q <= 0.02])):
        for s in sel.s:
            i = bar(s, T)
            r = trade(s, i, tp=None, sl=0.25, hold_h=72, side=side) if i is not None else None
            if r:
                res.append(dict(T=T, s=s, side=side, net=r["net"]))
R = pd.DataFrame(res)
for side, x in R.groupby("side"):
    mm, t, n = ct(x.net.values, x["T"].values)
    print(f"  сделки {'лонг' if side > 0 else 'шорт'} крайних 2% (срезы 00:00, стоп 25%, 72 ч): n={n}, {mm * 100:+.2f}% (t {t:+.1f}), "
          f"в плюсе {(x.net > 0).mean():.0%}")
