"""s280 — частота событий «каскад»: ход перпа за 60 мин (закрытия 15-мин свечей) ≤ −5% (и зеркало ≥ +5%) на отметке
15 мин, перп ≥ 7 сут, все 5 свечей с оборотом, первое у монеты за 24 ч. Доходы не считаются.
Запуск: python3 -I freq.py <файл свечей периода> <начало> <конец>"""
import pickle
import sys

import numpy as np
import pandas as pd

BAR, DAY = 900, 86400


def events(K, t0, t1, thr=0.05, side=-1, gap=DAY):
    out = []
    for s, a in K.items():
        t = a["t"].astype(np.int64)
        qv = a["qv"].astype(float)
        c = a["c"].astype(float)
        nz = np.flatnonzero(qv > 0)
        if len(nz) < 10:
            continue
        first = t[nz[0]]
        r = np.full(len(c), np.nan)
        r[4:] = c[4:] / c[:-4] - 1
        okv = np.ones(len(c), bool)
        for k in range(5):
            okv[k:] &= np.r_[np.zeros(k, bool), qv[: len(qv) - k] > 0][k:] if k else qv > 0
        cont = np.r_[np.zeros(4, bool), (t[4:] - t[:-4]) == 4 * BAR]
        te = t + BAR                                              # закрытие свечи
        m = cont & okv & np.isfinite(r) & (side * r >= thr) & (te >= t0) & (te < t1) & (te - first >= 7 * DAY)
        last = -10 ** 12
        for i in np.flatnonzero(m):
            if te[i] - last >= gap:
                out.append((s, int(te[i]), float(r[i])))
                last = te[i]
    return pd.DataFrame(out, columns=["s", "t", "r"])


if __name__ == "__main__":
    K = pickle.load(open(sys.argv[1], "rb"))
    t0 = int(pd.Timestamp(sys.argv[2], tz="UTC").timestamp()); t1 = int(pd.Timestamp(sys.argv[3], tz="UTC").timestamp())
    mo = (t1 - t0) / (30.44 * DAY)
    for side, lab in ((-1, "≤ −5%"), (1, "≥ +5%")):
        E = events(K, t0, t1, side=side)
        mid = np.median(E.t)
        wk = pd.Series(1, index=E.t // (7 * DAY)).groupby(level=0).sum()
        print(f"{lab}: {len(E)} событий, {len(E) / mo:.0f} в мес., монет {E.s.nunique()}, "
              f"в худшую неделю {wk.max()} ({wk.max() / len(E):.0%}), ≤ −10%/≥ +10%: {(np.abs(E.r) >= 0.10).sum()}")
