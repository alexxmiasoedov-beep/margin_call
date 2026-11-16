"""s62 — рост при отрицательном фандинге, шорт между начислениями (гипотеза — ВЫВОДЫ.md, записана до расчёта). Начисление
в T (интервал 4 или 8 ч, s2/fund2y.pkl), ставка в (−1%, −0,05%], фьючерс за 24 ч до T вырос ≥ 20%; не чаще раза в 24 ч на
монету. Шорт на закрытии 15-мин свечи, закончившейся в T + 15 мин; выход через 2 ч или за 30 мин до следующего начисления;
стоп +15%, без тейка. Плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402


def main():
    FU = pickle.load(open("s2/fund2y.pkl", "rb"))
    rows = []
    for s, f in FU.items():
        if s not in K:
            continue
        a = np.asarray(f, dtype=float)
        if a.ndim != 2 or not len(a):
            continue
        t = K[s]["t"].astype(np.int64); c = K[s]["c"].astype(float); qv = K[s]["qv"]
        last = -1e18
        for T, ih, rate in a:
            T = int(T)
            if ih not in (4, 8) or not (-0.01 < rate <= -0.0005) or T - last < 86400:
                continue
            j = int(np.searchsorted(t, T))                          # свеча, открывшаяся в T (закрытие T + 15 мин)
            if j >= len(t) or t[j] != T or j < 96 or qv[j] <= 0:
                continue
            jb = j - 1                                             # последняя свеча до T (закрытие в T)
            if c[jb - 96] <= 0 or c[jb] / c[jb - 96] - 1 < 0.20:
                continue
            last = T
            d = dict(s=s, t=T, rate=rate, ih=ih)
            for nm, hold in (("h2", 2.0), ("hnext", ih - 0.75)):
                x = trade(s, j, tp=None, sl=0.15, hold_h=hold)
                d[nm] = x["net"] if x else np.nan
                p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(s, j - dd * 96, tp=None, sl=0.15, hold_h=hold))]
                d["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s62/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий: {len(X)} ({len(X) / months:.1f} в месяц); интервал 4 ч: {(X.ih == 4).sum()}, 8 ч: {(X.ih == 8).sum()}")
    for col, lab in (("h2", "выход через 2 ч (основной)"), ("hnext", "выход за 30 мин до следующего начисления")):
        x = X[X[col].notna()]
        m, t_, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
        h1, h2 = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
        print(f"  {lab:42s} n={n:4d} {m:+6.2%} (t {t_:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} | половины {h1:+6.2%} / {h2:+6.2%}"
              f" | плацебо {x['pl_' + col].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
