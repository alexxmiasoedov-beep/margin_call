"""s172 — перебор правил из 1–3 условий «признак ≤ / ≥ порог» на событиях «займ ускорился» (метод — ВЫВОДЫ.md, записан до
расчёта; основа — «бомба» research/s7/bombe.py). Пороги — квинтили признака на отрезке A; правила с ≥ 150 событиями на A;
2000 лучших по t на A → отсев на B (средний доход > 0 и выше среднего всех событий B) → итог на C. Контроль — те же шаги
на исходах, перемешанных внутри месяца. Запуск из /home/user/mc_data:
python3 <repo>/research/s172/bombe.py <исход: n7|n2> [shuffle <seed>]"""
import datetime
import sys
import time

import numpy as np
import pandas as pd

UTC = datetime.timezone.utc
COL = sys.argv[1]; SHUF = len(sys.argv) > 2 and sys.argv[2] == "shuffle"
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 0
TA = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp(); TB = datetime.datetime(2026, 4, 1, tzinfo=UTC).timestamp()
MINN, TOPN = 150, 2000
OUTC = {"n7", "n7h", "n2", "n2h"}


def score(n, s, q):
    m = s / np.maximum(n, 1); var = np.maximum(q / np.maximum(n, 1) - m * m, 1e-12)
    return m / np.sqrt(var / np.maximum(n, 1))


def main():
    D = pd.read_pickle("s172_feat.pkl").sort_values("T").reset_index(drop=True)
    D = D[D[COL].notna()].reset_index(drop=True)
    seg = np.where(D["T"] < TA, 0, np.where(D["T"] < TB, 1, 2))
    y = D[COL].to_numpy(np.float64).copy()
    if SHUF:
        rng = np.random.default_rng(SEED); mon = pd.to_datetime(D["T"], unit="s").dt.to_period("M").astype(str).to_numpy()
        for m in np.unique(mon):
            ix = np.flatnonzero(mon == m); y[ix] = y[rng.permutation(ix)]
    FE = [c for c in D.columns if c not in OUTC | {"s", "T"} and pd.api.types.is_numeric_dtype(D[c])]
    A = seg == 0
    conds, names = [], []
    for f in FE:
        x = D[f].to_numpy(np.float64)
        xa = x[A & np.isfinite(x)]
        if len(xa) < 200 or np.unique(xa).size < 3:
            continue
        for q in sorted(set(np.round(np.quantile(xa, [0.2, 0.4, 0.6, 0.8]), 10))):
            lo = (x <= q) & np.isfinite(x); hi = (x >= q) & np.isfinite(x)
            for m, nm in ((lo, f"{f} ≤ {q:.4g}"), (hi, f"{f} ≥ {q:.4g}")):
                if 0.05 < m[A].mean() < 0.95:
                    conds.append(m); names.append(nm)
    C = np.array(conds, dtype=np.float32); nC = len(C)
    Y = y.astype(np.float32)
    print(f"{COL}: событий A/B/C = {(seg == 0).sum()}/{(seg == 1).sum()}/{(seg == 2).sum()}; признаков {len(FE)}, условий {nC}; "
          f"перемешано: {SHUF} {SEED if SHUF else ''}", flush=True)
    t0 = time.time()
    CA = C[:, A]; YA = Y[A]; YA2 = YA ** 2
    n1 = CA.sum(1); cand = []
    z1 = score(n1, CA @ YA, CA @ YA2)
    cand += [(z1[i], (i,)) for i in np.flatnonzero(n1 >= MINN)]
    N2 = CA @ CA.T; S2 = (CA * YA) @ CA.T; Q2 = (CA * YA2) @ CA.T
    iu = np.triu_indices(nC, 1); ok = N2[iu] >= MINN
    z2 = score(N2[iu], S2[iu], Q2[iu])
    cand += [(z2[k], (iu[0][k], iu[1][k])) for k in np.flatnonzero(ok)]
    best3 = []
    for a in range(nC):
        Ma = CA * CA[a]
        if Ma.sum() < MINN:
            continue
        N3 = Ma @ CA.T; Sa = (Ma * YA) @ CA.T; Qa = (Ma * YA2) @ CA.T
        si, sj = iu; sel = (si > a) & (N3[si, sj] >= MINN)
        if not sel.any():
            continue
        z = score(N3[si[sel], sj[sel]], Sa[si[sel], sj[sel]], Qa[si[sel], sj[sel]])
        for k in np.argsort(-z)[:100]:
            best3.append((z[k], (a, si[sel][k], sj[sel][k])))
    cand += best3
    cand.sort(key=lambda x: -x[0])
    print(f"правил-кандидатов {len(cand)} (одиночных {int((n1 >= MINN).sum())}, пар {int(ok.sum())}, троек {len(best3)}); "
          f"{time.time() - t0:.0f} с", flush=True)
    TOP = cand[:TOPN]
    masks = np.array([np.prod(C[list(ix)], axis=0) for _, ix in TOP], dtype=np.float32)
    res = {}
    for S in (0, 1, 2):
        sel = seg == S; M = masks[:, sel]; n = M.sum(1); s = M @ Y[sel]; q = M @ (Y[sel] ** 2)
        res[S] = (n, s / np.maximum(n, 1), score(n, s, q))
    R = pd.DataFrame({"правило": [" & ".join(names[i] for i in ix) for _, ix in TOP], "z_A": [z for z, _ in TOP],
                      "n_A": res[0][0], "m_A": res[0][1], "n_B": res[1][0], "m_B": res[1][1], "z_B": res[1][2],
                      "n_C": res[2][0], "m_C": res[2][1], "z_C": res[2][2]})
    base = {S: float(Y[seg == S].mean()) for S in (0, 1, 2)}
    passB = (R.m_B > 0) & (R.m_B > base[1]) & (R.n_B >= 30)
    P = R[passB]
    print(f"все события: A {base[0]:+.2%}, B {base[1]:+.2%}, C {base[2]:+.2%}")
    print(f"из {len(R)} лучших по A прошли отсев на B: {passB.sum()}")
    if len(P):
        best = P.sort_values("z_B", ascending=False).iloc[0]
        print(f"у прошедших на C: среднее {P.m_C.mean():+.2%} на сделку, в плюсе {(P.m_C > 0).mean():.0%}, выше всех событий C "
              f"{(P.m_C > base[2]).mean():.0%}; сделок на C в среднем {P.n_C.mean():.0f}")
        print(f"лучшее по B правило (выбрано до C): {best['правило']} | A {best.m_A:+.2%} (n {best.n_A:.0f}) | B {best.m_B:+.2%} "
              f"(n {best.n_B:.0f}, t {best.z_B:+.1f}) | C {best.m_C:+.2%} (n {best.n_C:.0f}, t {best.z_C:+.1f})")
    R.to_pickle(f"s172_bombe_{COL}{'_shuf' + str(SEED) if SHUF else ''}.pkl")
    if not SHUF and len(P):
        pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 100)
        T = P.sort_values("z_B", ascending=False).head(15)
        print(T.assign(**{c: T[c].round(4) for c in ("m_A", "m_B", "m_C", "z_A", "z_B", "z_C")}).to_string(index=False))


if __name__ == "__main__":
    main()
