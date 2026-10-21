"""«Бомба»: полный перебор правил из 1–3 условий «признак ≤ / ≥ порог» (пороги — квинтили на отрезке поиска) для заданного
исхода (сделка с тейком/стопом). Защита от случайных находок: поиск — отрезок A, отсев — B, проверка — C, которых поиск не видел;
тот же перебор на перемешанных исходах (внутри месяца) показывает, сколько «находок» даёт чистая случайность.
Запуск: python3 bombe.py <признаки.pkl> <исход> [перемешать]"""
import sys, time, datetime
import numpy as np, pandas as pd
UTC = datetime.timezone.utc
FN, COL = sys.argv[1], sys.argv[2]; SHUF = len(sys.argv) > 3 and sys.argv[3] == "shuffle"
D = pd.read_pickle(FN).sort_values("t").reset_index(drop=True)
D = D[D[COL].notna()].reset_index(drop=True)
import os
FILT = os.environ.get("FILTER")
if FILT: D = D.query(FILT).reset_index(drop=True)                     # подмножество событий, например "kshare < 0.2 and fshare < 0.1"
TA = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp(); TB = datetime.datetime(2026, 4, 1, tzinfo=UTC).timestamp()
seg = np.where(D.t < TA, 0, np.where(D.t < TB, 1, 2))
y = D[COL].to_numpy(np.float64).copy()
if SHUF:                                                              # перемешиваем исходы внутри каждого месяца
    rng = np.random.default_rng(int(sys.argv[4]) if len(sys.argv) > 4 else 0); mon = pd.to_datetime(D.t, unit="s").dt.to_period("M").astype(str).to_numpy()
    for m in np.unique(mon):
        ix = np.flatnonzero(mon == m); y[ix] = y[rng.permutation(ix)]
OUT = [c for c in D.columns if c.startswith(("S_", "L_")) or c in ("mfe_s24", "mae_s24", "mfe_s48", "mae_s48", "ret48", "ret24", "ret4", "full")]
FE = [c for c in D.columns if c not in OUT + ["s", "t", "i", "y", "jK", "iK"] and pd.api.types.is_numeric_dtype(D[c])]
A = seg == 0
conds, names = [], []
for f in FE:
    x = D[f].to_numpy(np.float64)
    xa = x[A & ~np.isnan(x)]
    if len(xa) < 200 or np.unique(xa).size < 3: continue
    for q in sorted(set(np.round(np.quantile(xa, [0.2, 0.4, 0.6, 0.8]), 10))):
        lo = (x <= q) & ~np.isnan(x); hi = (x >= q) & ~np.isnan(x)
        for m, nm in ((lo, f"{f} ≤ {q:.4g}"), (hi, f"{f} ≥ {q:.4g}")):
            if 0.05 < m[A].mean() < 0.95: conds.append(m); names.append(nm)
C = np.array(conds, dtype=np.float32); nC = len(C)
win = (y > 0).astype(np.float32); Y = y.astype(np.float32)
tp, sl = (int(v) for v in COL.split("_")[1:]); BE = sl / (tp + sl)
print(f"{COL}: безубыточный винрейт {BE:.1%}; событий A/B/C = {(seg == 0).sum()}/{(seg == 1).sum()}/{(seg == 2).sum()}; условий {nC}; перемешано: {SHUF}", flush=True)
def stats(mask_rows, S):            # S — сегмент: суммы по правилам (строки mask_rows: матрица правил × событий)
    sel = seg == S
    M = mask_rows[:, sel]; n = M.sum(1); s = M @ Y[sel]; w = M @ win[sel]; s2 = M @ (Y[sel] ** 2)
    return n, s, w, s2
MINN = 60
res = []
t0 = time.time()
CA = C[:, A]; YA = Y[A]; WA = win[A]; YA2 = YA ** 2
# одиночные и пары — одним матричным умножением
n1 = CA.sum(1); s1 = CA @ YA
N2 = CA @ CA.T; S2 = (CA * YA) @ CA.T; Q2 = (CA * YA2) @ CA.T
iu = np.triu_indices(nC, 1)
def score(n, s, q):
    m = s / np.maximum(n, 1); var = np.maximum(q / np.maximum(n, 1) - m * m, 1e-9); return m / np.sqrt(var / np.maximum(n, 1))
cand = []
z1 = score(n1, s1, CA @ YA2)
for i in np.flatnonzero(n1 >= MINN): cand.append((z1[i], (i,)))
z2 = score(N2[iu], S2[iu], Q2[iu]); ok = N2[iu] >= MINN
for k in np.flatnonzero(ok): cand.append((z2[k], (iu[0][k], iu[1][k])))
print(f"пары: {ok.sum()} правил с ≥ {MINN} сделками на A, {time.time() - t0:.0f} с", flush=True)
# тройки: для каждого условия a — матрица пар внутри подмножества a
best3 = []
for a in range(nC):
    Ma = CA * CA[a]
    if Ma.sum() < MINN: continue
    N3 = Ma @ CA.T                         # (условие a) ∧ i ∧ j  — через N[i, j] на подмножестве a
    Sa = (Ma * YA) @ CA.T; Qa = (Ma * YA2) @ CA.T
    sub_i, sub_j = np.triu_indices(nC, 1)
    sel = (sub_i > a) & (N3[sub_i, sub_j] >= MINN)
    if not sel.any(): continue
    n_ = N3[sub_i[sel], sub_j[sel]]; z = score(n_, Sa[sub_i[sel], sub_j[sel]], Qa[sub_i[sel], sub_j[sel]])
    top = np.argsort(-z)[:200]
    for k in top: best3.append((z[k], (a, sub_i[sel][k], sub_j[sel][k])))
    if a % 100 == 0: print(f"  тройки: условие {a}/{nC}, {time.time() - t0:.0f} с", flush=True)
cand += best3
cand.sort(key=lambda x: -x[0])
print(f"всего правил-кандидатов: {len(cand)}; перебор за {time.time() - t0:.0f} с", flush=True)
# отсев: 2000 лучших по A → проверка на B (среднее > 0 и винрейт выше безубыточного) → итог на C
TOP = cand[:2000]
masks = np.array([np.prod(C[list(ix)], axis=0) for _, ix in TOP], dtype=np.float32)
out = []
for S in (0, 1, 2):
    n, s, w, _ = stats(masks, S); out.append((n, s / np.maximum(n, 1), w / np.maximum(n, 1)))
R = pd.DataFrame({"правило": [" & ".join(names[i] for i in ix) for _, ix in TOP], "z_A": [z for z, _ in TOP],
                  "n_A": out[0][0], "pnl_A": out[0][1], "wr_A": out[0][2], "n_B": out[1][0], "pnl_B": out[1][1], "wr_B": out[1][2],
                  "n_C": out[2][0], "pnl_C": out[2][1], "wr_C": out[2][2]})
passB = (R.pnl_B > 0) & (R.wr_B > BE) & (R.n_B >= 20)
print(f"\nиз 2000 лучших по A прошли отсев на B: {passB.sum()}")
P = R[passB]
if len(P):
    print(f"у прошедших на C (не виденном): среднее {P.pnl_C.mean() * 100:+.2f}% на сделку, в плюсе {(P.pnl_C > 0).mean():.0%}, "
          f"винрейт {P.wr_C.mean():.1%} (безубыточный {BE:.1%}); сделок на C в среднем {P.n_C.mean():.0f}")
allC = Y[seg == 2]; print(f"для сравнения все события на C: {allC.mean() * 100:+.2f}%, винрейт {(allC > 0).mean():.1%}")
R.to_pickle(FN.replace(".pkl", f"_{COL}{'_f' if FILT else ''}{'_shuf' if SHUF else ''}_bombe.pkl"))
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 90)
print(P.head(12).assign(**{c: P[c].round(3) for c in ("pnl_A", "pnl_B", "pnl_C", "wr_A", "wr_B", "wr_C", "z_A")}).to_string(index=False))
