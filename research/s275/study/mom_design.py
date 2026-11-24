"""s275 — замысел Г1 «остаточный моментум ликвидных альтов за сутки» на отрезке замысла 01.10.2022–01.10.2023.
Описательно: наклон «остаток за прошлые 24 ч → остаток за следующие 24 ч» по месяцам и по группам ликвидности,
средний остаток следующих 24 ч после хода ≥ 2σ (σ — СО суточных сумм остатка в прошлом месяце), частота таких ходов.
Срезы — каждые 4 ч (00, 04, …, 20 UTC). Без комиссий, стопов и правил выхода; на других отрезках не считается.
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/mom_design.py → OUT/mom_design.txt"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DESIGN, H, OUT, load_k, panel, perps, ts, universe  # noqa: E402
from leadlag_design import alt_factor, month_starts  # noqa: E402
from cond_design import rsum  # noqa: E402

PER = "2022–2024"
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def main():
    K = load_k(PER)
    P = perps(K)
    LR = universe(K, P, PER)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    t0, t1 = DESIGN
    T, LC, QV = panel(K, P, t0, t1, H)
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = alt_factor(R, QV, iB, 24)
    btc = R[iB]
    X = np.column_stack([np.ones(R.shape[1]), btc, alt])
    MS = month_starts()
    rows = []
    for mi in range(len(MS) - 1):
        a0, a1 = MS[mi], MS[mi + 1]
        f0 = MS[mi - 1] if mi > 0 else ts("2022-10-01")
        ev = (T > a0) & (T <= a1); fit = (T > f0) & (T <= a0)
        U = [p for p in sorted(LR.get(int(a0 // 86400 * 86400), ())) if p in pidx and p != "BTC"]
        liq = {p: QV[pidx[p], fit].sum() for p in U}
        rank = {p: r for r, p in enumerate(sorted(U, key=lambda p: -liq[p]))}
        for p in U:
            y = R[pidx[p]]
            ok = fit & np.isfinite(y) & np.isfinite(X).all(1)
            if ok.sum() < 300:
                continue
            b, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
            e = y - X @ b
            s24 = rsum(e, 24)
            sig = np.nanstd(s24[fit][::24])
            for i in np.flatnonzero(ev):
                if (T[i] % 14400) != 0 or not np.isfinite(s24[i]):
                    continue
                f = e[i + 1:i + 25]
                fut = f.sum() if len(f) == 24 and np.isfinite(f).all() else np.nan
                rows.append((mi, rank[p], s24[i], s24[i] / sig, fut))
    A = np.array(rows, dtype=float)
    say("s275 — замысел Г1 (остаточный моментум за сутки), отрезок замысла 01.10.2022–01.10.2023, срезы каждые 4 ч")
    for lo, hi, nm in ((0, 30, "топ-30"), (30, 100, "31–100")):
        g = A[(A[:, 1] >= lo) & (A[:, 1] < hi) & np.isfinite(A[:, 4])]
        b = np.sum(g[:, 2] * g[:, 4]) / np.sum(g[:, 2] ** 2)
        bm = []
        for mi in range(len(MS) - 1):
            gm = g[g[:, 0] == mi]
            bm.append(np.sum(gm[:, 2] * gm[:, 4]) / np.sum(gm[:, 2] ** 2))
        say(f"\n## {nm}: наклон 24→24 {b:+.3f}; по месяцам: " + ", ".join(f"{x:+.2f}" for x in bm) +
            f" (в плюсе {np.sum(np.array(bm) > 0)} из {len(bm)})")
        for thr in (2, 3):
            for sgn, nm2 in ((1, "вверх"), (-1, "вниз")):
                m = (g[:, 3] * sgn) >= thr
                months = 11
                say(f"  ход {nm2} ≥ {thr}σ: срезов {m.sum()} ({m.sum() / months:.0f} в мес.; монето-суток ≈ "
                    f"{m.sum() / 6 / months:.0f} в мес.), ход медиана {np.median(g[m, 2]):+.2%}; следующие 24 ч в сторону хода: "
                    f"среднее {np.mean(g[m, 4] * sgn):+.2%}, медиана {np.median(g[m, 4] * sgn):+.2%}, СО {np.std(g[m, 4]):.2%}")
    open(f"{OUT}/mom_design.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
