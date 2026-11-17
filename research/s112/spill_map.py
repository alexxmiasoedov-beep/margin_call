"""s112 — изучение: перетекание внимания внутри нарратива. После пампа лидера (+15% за ≤ 2 ч из покоя, s49/trades.pkl)
берутся 5 соседей с наибольшей корреляцией часовых остатков (доход монеты минус индекс альтов s103) за 60 сут до пампа
(без последних суток), корреляция ≥ 0,2, сосед ликвиден и за окно пампа вырос меньше чем на 5%. Лонг соседа на закрытии
свечи пампа на 6 / 24 / 72 ч (стоп 15%, s15/common.trade). ТОЛЬКО первая половина (вход до 01.12.2025 − 3 сут): разбор
для гипотез. Плацебо — тот же сосед за 45/90/135 сут. Запуск из папки с данными: python3 <repo>/research/s112/spill_map.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s103", "s105"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402
from beta import index  # noqa: E402
from jumps_test import SKIP  # noqa: E402

HOLDS = (6, 24, 72)


def main():
    tI, I, _, _ = index()
    t = K["BTC"]["t"]; n = len(t)
    syms = [s for s in K if s not in SKIP and len(K[s]["t"]) == n]
    C = np.vstack([K[s]["c"].astype(np.float64)[3::4] for s in syms])            # часовые закрытия
    Q = np.vstack([K[s]["qv"].astype(np.float64) for s in syms])
    Ih = I[3::4]
    R = np.diff(np.log(np.maximum(C, 1e-12)), axis=1) - np.diff(np.log(Ih))[None, :]
    hclose = t[3::4] + 900                                                          # время закрытия часа
    pos = {s: k for k, s in enumerate(syms)}
    P = pd.read_pickle("s49/trades.pkl")
    P = P[(P.t + 3 * DAY < CUT) & P.s.isin(pos)].sort_values("t")
    rows = []
    for s, T, kr, share in zip(P.s, P.t.astype(float), P.kr, P.share):
        h = int(np.searchsorted(hclose, T, "right")) - 1                            # последний закрытый час
        if h < 61 * 24:
            continue
        w0, w1 = h - 60 * 24, h - 24
        X = R[:, w0:w1]
        lead = X[pos[s]]
        ok = np.isfinite(X).all(axis=1) & (np.nanstd(X, axis=1) > 0)
        i15 = int(np.searchsorted(t + 900, T))
        v7 = Q[:, max(0, i15 - 672):i15 + 1].sum(axis=1) / 7
        cand = []
        for k in np.flatnonzero(ok & (v7 >= 5e6)):
            sp = syms[k]
            if sp == s:
                continue
            lo, hi = live(sp)
            if T - 30 * DAY < lo or T + 4 * DAY > hi:
                continue
            cr = float(np.corrcoef(lead, X[k])[0, 1])
            if cr >= 0.2:
                cand.append((cr, sp))
        cand.sort(reverse=True)
        for cr, sp in cand[:5]:
            i = idx_at(sp, T)
            if i is None:
                continue
            c = K[sp]["c"]
            mv = float(c[i] / c[i - 8] - 1)                                          # ход соседа за окно пампа (2 ч)
            d = dict(lead=s, s=sp, t=T, corr=cr, mv=mv, kr=kr, share=share)
            for hh in HOLDS:
                x = trade(sp, i, tp=None, sl=0.15, hold_h=hh, side=1)
                d[f"L{hh}"] = x["net"] if x else np.nan
                j0 = int(np.searchsorted(tI + 900, T)); j1 = min(j0 + hh * 4, len(I) - 1)
                d[f"m{hh}"] = I[j1] / I[j0] - 1
                p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(sp, T - dd * DAY)) is not None
                     and (y := trade(sp, j, tp=None, sl=0.15, hold_h=hh, side=1))]
                d[f"pl{hh}"] = np.mean(p) if p else np.nan
            rows.append(d)
    D = pd.DataFrame(rows)
    D.to_pickle("s112/spill_first.pkl")
    months = (D.t.max() - D.t.min()) / (30.4 * DAY)
    print(f"первая половина: пампов-лидеров {D.lead.nunique() and D.groupby(['lead', 't']).ngroups}, сделок с соседями {len(D)} "
          f"({len(D) / months:.0f} в мес.); медианная корреляция {D['corr'].median():.2f}; ход соседа за окно пампа "
          f"медиана {D.mv.median():+.1%}")
    for lab, x in (("все соседи", D), ("сосед вырос < 5% за окно", D[D.mv < 0.05]), ("сосед вырос ≥ 5%", D[D.mv >= 0.05]),
                   ("корреляция ≥ 0,4", D[D["corr"] >= 0.4]), ("памп с долей Кореи ≥ 20%", D[D.kr >= 0.2]),
                   ("памп с долей спота ≥ 26%", D[D.share >= 0.26])):
        cells = []
        for hh in HOLDS:
            y = x[x[f"L{hh}"].notna()]
            m, tt, nn = ct(y[f"L{hh}"], y.t); dp, tp, _ = ct(y[f"L{hh}"] - y[f"pl{hh}"], y.t)
            ex = (y[f"L{hh}"] - y[f"m{hh}"]).mean()
            cells.append(f"{hh} ч: {m:+.2%} (t {tt:+.1f}) сверх индекса {ex:+.2%}, сверх плацебо {dp:+.2%} (t {tp:+.1f})")
        print(f"  {lab:28s} n={len(x):5d} | " + " | ".join(cells))


if __name__ == "__main__":
    main()
