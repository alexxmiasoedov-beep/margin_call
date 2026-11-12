"""Корзина по модели (dev — только первая половина): LightGBM на рангах признаков (как в g9_model) учится на первой
половине до CUT − 120 сут; на проверочных днях (последние 117 суток первой половины) в 00:00 UTC — шорт нижнего дециля
прогноза и лонг верхнего; сделки через common.trade (15-мин свечи, комиссия 0,1%, фактический фандинг, стоп с
проскальзыванием), держим 72 ч. Плацебо — случайные монеты среза того же числа. Запуск: python3 g17_basket.py dev"""
import sys
import numpy as np, pandas as pd
import lightgbm as lgb
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT
from common23 import K, ct, trade

MODE = sys.argv[1] if len(sys.argv) > 1 else "dev"
FEATS = ["R", "R72", "R7d", "PHI", "D", "B", "A", "TS", "VC", "PMW", "dPM", "F8", "ETA3", "DH30", "DL30", "NPUMP", "AGE", "Vb", "lam"]
L = pd.read_pickle("s23/long4h.pkl")
L = L[L.Y72.notna()].copy()
g = L.groupby("T")
for f in FEATS:
    L["r_" + f] = g[f].rank(pct=True) - 0.5
L["r_Y72"] = g["Y72"].rank(pct=True) - 0.5
X = ["r_" + f for f in FEATS]
L[X] = L[X].fillna(0.0)
if MODE == "dev":
    tr = L[L["T"] < CUT - 120 * 86400]; te = L[(L["T"] >= CUT - 117 * 86400) & (L["T"] < CUT) & (L["T"] % 86400 == 0)]
else:
    tr = L[L["T"] < CUT - 3 * 86400]; te = L[(L["T"] >= CUT) & (L["T"] % 86400 == 0)]
m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=7, min_child_samples=5000, subsample=0.7, subsample_freq=1,
                      colsample_bytree=0.8, reg_lambda=10, verbose=-1).fit(tr[X], tr["r_Y72"])
te = te.assign(p=m.predict(te[X]))
rng = np.random.default_rng(7)
idx_cache = {}


def bar(s, T):
    t = K[s]["t"]
    i = int(np.searchsorted(t, T - 900))
    return i if i < len(t) and t[i] + 900 == T else None


res = []
for T, q in te.groupby("T"):
    q = q.sort_values("p")
    n10 = max(1, len(q) // 10)
    groups = {"шорт D1": (q.head(n10), -1), "лонг D10": (q.tail(n10), 1),
              "шорт случайные": (q.iloc[rng.choice(len(q), n10, replace=False)], -1)}
    for nm, (sel, side) in groups.items():
        for s in sel.s:
            i = bar(s, T)
            if i is None:
                continue
            for sl in (None, 0.25, 0.5):
                r = trade(s, i, tp=None, sl=sl, hold_h=72, side=side)
                if r:
                    res.append(dict(T=T, s=s, grp=nm, sl=sl, net=r["net"], why=r["why"]))
R = pd.DataFrame(res)
print(f"{MODE}: дней {te['T'].nunique()}, сделок {len(R)}")
for (grp, sl), x in R.groupby(["grp", R.sl.fillna(0)]):
    mm, t, n = ct(x.net, x["T"])
    print(f"  {grp:>15}, стоп {'нет' if not sl else f'{sl:.0%}'}: {n} сделок, в среднем {mm * 100:+.2f}% (t по дням {t:+.1f}), "
          f"медиана {x.net.median() * 100:+.2f}%, в плюсе {(x.net > 0).mean():.0%}, стопов {(x.why == 'стоп').mean():.0%}")
