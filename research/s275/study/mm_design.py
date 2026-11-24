"""s275 — скрытая связь «общий фонд или маркетмейкер» (теги CMC «<фонд>-portfolio») на отрезке замысла
01.10.2022–01.10.2023: средняя корреляция часовых остатков e1 у пар с общим тегом против всех пар, против пар одного
сектора; кросс-корреляция «монета портфеля сейчас → другие монеты портфеля в следующий час». Только описательная
статистика, доходы не считаются. Вселенная — топ-200 по обороту (как sector_design).
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/mm_design.py → OUT/mm_design.txt"""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DESIGN, H, OUT, load_k, panel, perps, sectors, ts, universe  # noqa: E402
from leadlag_design import alt_factor, month_starts  # noqa: E402

PER = "2022–2024"
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def main():
    K = load_k(PER)
    P = perps(K)
    SEC = sectors()
    PF = {r["perp"]: set(x for x in r["portfolios"].split("|") if x)
          for r in csv.DictReader(open(os.path.join(os.path.dirname(__file__), "..", "sectors.csv")))}
    LR = universe(K, P, PER, top=200)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    t0, t1 = DESIGN
    T, LC, QV = panel(K, P, t0, t1, H)
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = alt_factor(R, QV, iB, 24)
    btc = R[iB]
    X = np.column_stack([np.ones(R.shape[1]), btc, alt])
    MS = month_starts()
    acc = {}
    ll = {}
    for mi in range(len(MS) - 1):
        a0, a1 = MS[mi], MS[mi + 1]
        f0 = MS[mi - 1] if mi > 0 else ts("2022-10-01")
        ev = (T > a0) & (T <= a1); fit = (T > f0) & (T <= a0)
        U = [p for p in sorted(LR.get(int(a0 // 86400 * 86400), ())) if p in pidx and p != "BTC"]
        U = [p for p in U if np.isfinite(R[pidx[p], ev]).mean() >= 0.9 and np.isfinite(R[pidx[p], fit]).mean() >= 0.9]
        E = {}
        for p in U:
            y = R[pidx[p]]
            ok = fit & np.isfinite(y) & np.isfinite(X).all(1)
            b, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
            E[p] = (y - X @ b)[ev]
        names = sorted(E)
        M = np.array([E[p] for p in names]); ok = np.isfinite(M).all(0)
        C = np.corrcoef(M[:, ok])
        iu = np.triu_indices(len(names), 1)
        allc = C[iu]
        acc.setdefault("все пары", []).append(np.mean(allc))
        same_sec = np.array([SEC.get(names[a], {}).get("sector") == SEC.get(names[b], {}).get("sector") != ""
                             for a, b in zip(*iu)])
        acc.setdefault("один сектор", []).append(np.mean(allc[same_sec]))
        tags = {}
        for p in names:
            for t in PF.get(p, ()):
                tags.setdefault(t, []).append(p)
        for t, mem in tags.items():
            if len(mem) < 5:
                continue
            ix = [names.index(p) for p in mem]
            sub = C[np.ix_(ix, ix)][np.triu_indices(len(ix), 1)]
            acc.setdefault(t, []).append((np.mean(sub), len(mem)))
            # «монета сейчас → корзина других монет портфеля в следующий час»
            for j, p in enumerate(mem):
                others = [q for q in mem if q != p]
                with np.errstate(all="ignore"):
                    ob = np.nanmean(np.array([E[q] for q in others]), axis=0)
                x = E[p][:-1]; y = ob[1:]
                okk = np.isfinite(x) & np.isfinite(y)
                s = ll.setdefault(t, np.zeros(3))
                s += [np.sum(x[okk] * y[okk]), np.sum(x[okk] ** 2), np.sum(y[okk] ** 2)]
    say("s275 — общий фонд или маркетмейкер (теги CMC «…-portfolio»), отрезок замысла 01.10.2022–01.10.2023, топ-200")
    say(f"  средняя корреляция часовых остатков e1: все пары {np.mean(acc['все пары']):+.3f}, один сектор "
        f"{np.mean(acc['один сектор']):+.3f}")
    rows = []
    for t, v in acc.items():
        if t in ("все пары", "один сектор") or len(v) < 6:
            continue
        rows.append((np.mean([x for x, _ in v]), t, np.mean([n for _, n in v]), len(v)))
    for m, t, n, k in sorted(rows, reverse=True):
        s = ll.get(t, np.zeros(3))
        rho = s[0] / np.sqrt(s[1] * s[2]) if s[1] > 0 and s[2] > 0 else np.nan
        say(f"  {t:32s}: корреляция внутри {m:+.3f} (членов в среднем {n:.1f}, месяцев {k}); "
            f"«монета → другие монеты портфеля через час» ρ {rho:+.3f}")
    open(f"{OUT}/mm_design.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
