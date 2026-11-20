"""s216 — перебор правил из 1–3 условий «признак ≤ / ≥ порог» на сетке 4 ч (метод — ВЫВОДЫ.md, записан до расчёта; основа —
s172/bombe.py). t — по кластерам-неделям. Пороги — квинтили на A; правила с ≥ 150 наблюдениями на A; 2000 лучших по t на A →
отсев на B (среднее > 0 и выше всех наблюдений B) → итог на C. Контроль — исходы, перемешанные внутри месяца.
Запуск из /home/user/mc_data: python3 <repo>/research/s216/bombe.py <исход: s4|s24|s48|s168|l4|l24|l48|l168> [shuffle <seed>]"""
import datetime
import os
import sys
import time

import numpy as np
import pandas as pd

UTC = datetime.timezone.utc
TA = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp(); TB = datetime.datetime(2026, 4, 1, tzinfo=UTC).timestamp()
MINN, TOPN, TOP2 = 150, 2000, 300
if os.environ.get("TA"):                            # s219: свои отрезки, минимум наблюдений и порог t на B
    TA = datetime.datetime.fromisoformat(os.environ["TA"]).replace(tzinfo=UTC).timestamp()
    TB = datetime.datetime.fromisoformat(os.environ["TB"]).replace(tzinfo=UTC).timestamp()
MINN = int(os.environ.get("MINN", MINN))
ZB = float(os.environ.get("ZB", "-inf"))
OUTC = {"s4", "s24", "s48", "s168", "l4", "l24", "l48", "l168"}
WEEK = 7 * 86400
PFX = os.environ.get("PFX", "s216")               # s218 и далее — тот же перебор на своём файле признаков
SPARSE = os.environ.get("SPARSE") == "1"           # условия для редких признаков (s218, уточнение до перебора)


def zclust(N, S, axis=0):
    """Среднее и t по кластерам: N, S — числа и суммы по кластерам (ось axis). → (n, m, z)."""
    n = N.sum(axis); s = S.sum(axis); m = s / np.maximum(n, 1)
    mm = np.expand_dims(m, axis)
    v = ((S - mm * N) ** 2).sum(axis) / np.maximum(n, 1) ** 2
    return n, m, m / np.sqrt(np.maximum(v, 1e-18))


def week_mat(T, sel):
    w = (T[sel] // WEEK).astype(np.int64)
    u, inv = np.unique(w, return_inverse=True)
    W = np.zeros((sel.sum(), len(u)), np.float32); W[np.arange(sel.sum()), inv] = 1
    return W, inv, len(u)


def run(col, shuf=False, seed=0, verbose=True):
    D = pd.read_pickle(f"{PFX}_feat.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    D = D[D[col].notna()].reset_index(drop=True)
    T = D["T"].to_numpy(np.int64)
    seg = np.where(T < TA, 0, np.where(T < TB, 1, 2))
    y = D[col].to_numpy(np.float64).copy()
    if shuf:
        rng = np.random.default_rng(seed)
        mon = pd.to_datetime(D["T"], unit="s").dt.to_period("M").astype(str).to_numpy()
        for m in np.unique(mon):
            ix = np.flatnonzero(mon == m); y[ix] = y[rng.permutation(ix)]
    FE = [c for c in D.columns if c not in OUTC | {"s", "T"} and not c.startswith(("y_", "u_"))
          and pd.api.types.is_numeric_dtype(D[c])]
    A = seg == 0
    conds, names = [], []
    for f in FE:
        x = D[f].to_numpy(np.float64)
        xa = x[A & np.isfinite(x)]
        if len(xa) < 300 or np.unique(xa).size < 2:
            continue
        u, cnt = np.unique(xa, return_counts=True)
        if SPARSE and cnt.max() >= 0.8 * len(xa):                # редкий признак (s218): «событие есть» и квинтили событий
            mode = u[cnt.argmax()]; ev = xa[xa != mode]; up = mode <= ev.min() if len(ev) else True
            cand = [((x != mode) & np.isfinite(x), f"{f} ≠ {mode:.4g}")]
            if len(ev) >= 300:
                for q in sorted(set(np.round(np.quantile(ev, [0.2, 0.4, 0.6, 0.8]), 10))):
                    m = ((x >= q) if up else (x <= q)) & (x != mode) & np.isfinite(x)
                    cand.append((m, f"{f} {'≥' if up else '≤'} {q:.4g}"))
            for m, nm in cand:
                if m[A].sum() >= MINN and m[A].mean() < 0.95 and not any((m == c).all() for c in conds[-8:]):
                    conds.append(m); names.append(nm)
            continue
        for q in sorted(set(np.round(np.quantile(xa, [0.2, 0.4, 0.6, 0.8]), 10))):
            lo = (x <= q) & np.isfinite(x); hi = (x >= q) & np.isfinite(x)
            for m, nm in ((lo, f"{f} ≤ {q:.4g}"), (hi, f"{f} ≥ {q:.4g}")):
                if 0.05 < m[A].mean() < 0.95 and not any((m == c).all() for c in conds[-8:]):
                    conds.append(m); names.append(nm)
    C = np.array(conds, dtype=bool); nC = len(C)                 # bool: на s219 (570 тыс. наблюдений) float32 не помещался
    Y = y.astype(np.float32)
    t0 = time.time()
    CA = C[:, A].astype(np.float32); YA = Y[A]
    W, inv, nW = week_mat(T, A)
    # одиночные
    N1 = CA @ W; S1 = (CA * YA) @ W
    n1, _, z1 = zclust(N1, S1, axis=1)
    cand = [(z1[i], (i,)) for i in np.flatnonzero(n1 >= MINN)]
    # пары: по неделям
    N2 = np.zeros((nW, nC, nC), np.float32); S2 = np.zeros((nW, nC, nC), np.float32)
    for w in range(nW):
        r = inv == w
        Cw = CA[:, r]; N2[w] = Cw @ Cw.T; S2[w] = (Cw * YA[r]) @ Cw.T
    n2, _, z2 = zclust(N2, S2, axis=0)
    iu = np.triu_indices(nC, 1); ok = n2[iu] >= MINN
    zz = z2[iu]
    cand += [(zz[k], (iu[0][k], iu[1][k])) for k in np.flatnonzero(ok)]
    del N2, S2
    # тройки: продолжения лучших пар
    best2 = sorted(((zz[k], iu[0][k], iu[1][k]) for k in np.flatnonzero(ok)), key=lambda x: -x[0])[:TOP2]
    seen = set()
    for _, a, b in best2:
        M = CA[a] * CA[b]
        N3 = (CA * M) @ W; S3 = (CA * (M * YA)) @ W
        n3, _, z3 = zclust(N3, S3, axis=1)
        for c in np.flatnonzero(n3 >= MINN):
            key = tuple(sorted((a, b, c)))
            if c in (a, b) or key in seen:
                continue
            seen.add(key); cand.append((z3[c], key))
    cand.sort(key=lambda x: -x[0])
    if verbose:
        print(f"{col}: наблюдений A/B/C = {(seg == 0).sum()}/{(seg == 1).sum()}/{(seg == 2).sum()}; признаков {len(FE)}, "
              f"условий {nC}; правил {len(cand)}; {time.time() - t0:.0f} с; перемешано: {shuf} {seed if shuf else ''}", flush=True)
    TOP = cand[:TOPN]
    res = {}
    for S in (0, 1, 2):                                              # правила — кусками по 250, чтобы хватило памяти
        sel = seg == S
        Ws, _, _ = week_mat(T, sel)
        parts = []
        for k0 in range(0, len(TOP), 250):
            M = np.array([np.logical_and.reduce(C[list(ix)][:, sel], axis=0) for _, ix in TOP[k0:k0 + 250]], dtype=np.float32)
            parts.append(zclust(M @ Ws, (M * Y[sel]) @ Ws, axis=1))
        res[S] = tuple(np.concatenate([p_[i] for p_ in parts]) for i in range(3))
    R = pd.DataFrame({"правило": [" & ".join(names[i] for i in ix) for _, ix in TOP], "z_A": [z for z, _ in TOP],
                      "n_A": res[0][0], "m_A": res[0][1], "n_B": res[1][0], "m_B": res[1][1], "z_B": res[1][2],
                      "n_C": res[2][0], "m_C": res[2][1], "z_C": res[2][2]})
    base = {S: float(Y[seg == S].mean()) for S in (0, 1, 2)}
    passB = (R.m_B > 0) & (R.m_B > base[1]) & (R.n_B >= 30) & (R.z_B >= ZB)
    R["passB"] = passB
    R.attrs["base"] = base
    out = f"{PFX}_bombe_{col}{'_shuf' + str(seed) if shuf else ''}.pkl"
    R.to_pickle(out)
    P = R[passB]
    if verbose:
        print(f"все наблюдения: A {base[0]:+.2%}, B {base[1]:+.2%}, C {base[2]:+.2%}; прошли отсев на B: {passB.sum()} из {len(R)}")
        if len(P):
            best = P.sort_values("z_B", ascending=False).iloc[0]
            print(f"у прошедших на C: среднее {P.m_C.mean():+.2%}, в плюсе {(P.m_C > 0).mean():.0%}, выше всех C "
                  f"{(P.m_C > base[2]).mean():.0%}")
            print(f"лучшее по B (выбрано до C): {best['правило']} | A {best.m_A:+.2%} (n {best.n_A:.0f}, t {best.z_A:+.1f}) | "
                  f"B {best.m_B:+.2%} (n {best.n_B:.0f}, t {best.z_B:+.1f}) | C {best.m_C:+.2%} (n {best.n_C:.0f}, t {best.z_C:+.1f})",
                  flush=True)
    return R


if __name__ == "__main__":
    run(sys.argv[1], len(sys.argv) > 2 and sys.argv[2] == "shuffle", int(sys.argv[3]) if len(sys.argv) > 3 else 0)
