"""s113 и s114 — проверка гипотез s112 на всей истории (правила — ВЫВОДЫ.md в s113 и s114, записаны до проверки).
Соседи лидера пампа (s49/trades.pkl) — 5 монет с наибольшей корреляцией часовых остатков (минус индекс альтов s103)
за 60 сут до пампа без последних суток, корреляция ≥ 0,2, ликвидные, фьючерс старше 30 сут.
s113: соседи, выросшие за окно пампа на ≥ 5% → лонг 6 ч, стоп 15%. s114: лидер с долей Кореи ≥ 20% → шорт соседей
72 ч (и 24 ч), стоп 25%. Плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными после s103/beta.py:
python3 <repo>/research/s113/peers_test.py"""
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


def neighbours():
    tI, I, _, _ = index()
    t = K["BTC"]["t"]; n = len(t)
    syms = [s for s in K if s not in SKIP and len(K[s]["t"]) == n]
    C = np.vstack([K[s]["c"].astype(np.float64)[3::4] for s in syms])
    Q = np.vstack([K[s]["qv"].astype(np.float64) for s in syms])
    R = np.diff(np.log(np.maximum(C, 1e-12)), axis=1) - np.diff(np.log(I[3::4]))[None, :]
    hclose = t[3::4] + 900
    pos = {s: k for k, s in enumerate(syms)}
    P = pd.read_pickle("s49/trades.pkl"); P = P[P.s.isin(pos)].sort_values("t")
    out = []
    for s, T, kr in zip(P.s, P.t.astype(float), P.kr):
        h = int(np.searchsorted(hclose, T, "right")) - 1
        if h < 61 * 24:
            continue
        X = R[:, h - 60 * 24:h - 24]; lead = X[pos[s]]
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
            if i is not None:
                c = K[sp]["c"]
                out.append((s, sp, T, cr, float(c[i] / c[i - 8] - 1), kr, i))
    return pd.DataFrame(out, columns=["lead", "s", "t", "corr", "mv", "kr", "i"])


def run(N, side, hold, sl, gap_h):
    rows, last = [], {}
    for r in N.sort_values("t").itertuples():
        if r.t - last.get(r.s, -1e18) < gap_h * 3600:
            continue
        x = trade(r.s, r.i, tp=None, sl=sl, hold_h=hold, side=side)
        if not x:
            continue
        last[r.s] = r.t
        p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(r.s, r.t - dd * DAY)) is not None
             and (y := trade(r.s, j, tp=None, sl=sl, hold_h=hold, side=side))]
        rows.append(dict(s=r.s, t=r.t, net=x["net"], why=x["why"], pl=np.mean(p) if p else np.nan))
    return pd.DataFrame(rows)


def report(lab, D):
    months = (D.t.max() - D.t.min()) / (30.4 * DAY)
    print(f"\n{lab}: сделок {len(D)} ({len(D) / months:.1f} в мес.), стопов {(D.why == 'стоп').mean():.0%}")
    for nm, x in (("1-я половина (разбор)", D[D.t < CUT]), ("2-я половина (проверка)", D[D.t >= CUT]), ("вся история", D)):
        mm = max((x.t.max() - x.t.min()) / (30.4 * DAY), 1)
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        print(f"  {nm:24s} n={n:4d} ({n / mm:5.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(x.net > 0).mean():.0%} | "
              f"плацебо {x.pl.mean():+.2%}, разница {dp:+.2%} (t {tp:+.1f})")


def main():
    N = neighbours()
    N.to_pickle("s113/neighbours.pkl")
    report("s113 — лонг соседей, выросших ≥ 5% вместе с лидером, 6 ч, стоп 15%", run(N[N.mv >= 0.05], 1, 6, 0.15, 6))
    K20 = N[N.kr >= 0.2]
    report("s114 — шорт соседей корейского пампа, 72 ч, стоп 25% (основной)", run(K20, -1, 72, 0.25, 72))
    report("s114 — шорт соседей корейского пампа, 24 ч, стоп 25%", run(K20, -1, 24, 0.25, 24))


if __name__ == "__main__":
    main()
