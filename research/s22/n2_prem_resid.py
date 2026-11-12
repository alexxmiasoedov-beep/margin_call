"""Заметка 2 к Г7: «перп дороже индекса сверх уже оплаченного фандинга растёт дальше». Заметка возникла из регрессии
h7_carry.py, где из-за совпадения имён колонок мерой фандинга оказался будущий фандинг (исправлено 12.11). Здесь —
прямое правило, заданное заранее, на исправленной таблице s22/h7_panel.pkl: каждый день остаток ранга премии за 24 ч
после ранга фандинга за прошлые 3 суток (линейная регрессия рангов в поперечном срезе); лонг верхнего квинтиля остатка
на 7 суток (цена − фандинг − комиссия) к среднему по корзине; нижний квинтиль — для сравнения. t Ньюи–Уэста (6 лагов),
половины, годы. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import CUT, FEE
from h2_dtc import nw_t

if __name__ == "__main__":
    P = pd.read_pickle("s22/h7_panel.pkl").dropna(subset=["prem", "fav", "px7"])
    P["l7"] = P.px7 - P.f7 - FEE
    rows = []
    for d, g in P.groupby("d"):
        if len(g) < 25:
            continue
        rp, rf = g.prem.rank(pct=True).values, g.fav.rank(pct=True).values
        b = np.polyfit(rf, rp, 1); res = rp - np.polyval(b, rf)
        q = pd.Series(res).rank(pct=True).values; m = g.l7.mean()
        rows.append((d, g.l7.values[q > 0.8].mean() - m, g.l7.values[q <= 0.2].mean() - m))
    R = pd.DataFrame(rows, columns=["d", "hi", "lo"]); y = pd.to_datetime(R.d, unit="s").dt.year
    for col, nm in (("hi", "верхний квинтиль (премия сверх фандинга)"), ("lo", "нижний квинтиль")):
        x = R[col]
        print(f"{nm}: лонг 7 сут к среднему корзины {x.mean() * 100:+.2f}% (t НУ {nw_t(x):+.1f}; половины "
              f"{x[R.d < CUT].mean() * 100:+.2f}/{x[R.d >= CUT].mean() * 100:+.2f}%; " +
              ", ".join(f"{yy}: {x[y == yy].mean() * 100:+.2f}" for yy in sorted(y.unique())) + ")")
