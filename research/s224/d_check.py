"""s224b — проверка комитетов на свежем отрезке D (метод и порог — research/s224/ВЫВОДЫ.md, записаны до сбора данных).

Правила комитета (100 лучших по t на B из прошедших отсев) и порог голосов k выбираются, как в s223/committee.py, на старых
данных (A и B); условия переносятся на строки D с точными порогами, посчитанными на A (bombe.build(..., specs)).
D — входы с 22.10.2026 00:00 UTC по конец данных (файл s224/feat_D.pkl: часовая сетка, признаки и исходы — тем же кодом).
Порог: средний доход с хеджем на D > 0; на C + D вместе — t ≥ 3 по неделям, ≥ 20 сделок в месяц, лучше плацебо.
Запуск из /home/user/mc_data: python3 <repo>/research/s224/d_check.py <префикс файла признаков>:<исход>:<сетка, ч>[:<файл D>] …
(по умолчанию — s223:y_hs4:4; файл D по умолчанию — s224/feat_D.pkl, для s225 — свой файл с признаками s225)."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s216", "s223", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import bombe  # noqa: E402
import committee as CM  # noqa: E402

DAY = 86400
D0 = pd.Timestamp("2026-10-22", tz="UTC").timestamp()


def masks(F, specs):
    out = []
    for f, op, q in specs:
        x = F[f].to_numpy(float)
        out.append(((x <= q) if op == "le" else (x >= q)) & np.isfinite(x))
    return np.array(out, bool)


def check(prefix, col, grid_h, FD):
    F = pd.read_pickle(f"{prefix}_feat.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    D = F[F[col].notna()].reset_index(drop=True)
    T = D["T"].to_numpy(np.int64); seg = np.where(T < bombe.TA, 0, np.where(T < bombe.TB, 1, 2))
    y = D[col].to_numpy(float); end = D["u_e_" + col[2:]].to_numpy(float)
    specs = []
    C, _, _ = bombe.build(D, seg == 0, specs)
    assert len(specs) == len(C), "условия и их описания не совпали"
    R = pd.read_pickle(f"{prefix}_bombe_{col}.pkl")
    v, nP = CM.votes(R, C)
    k = CM.pick_k(v, seg, D, y, end)[0]
    tkC = CM.honest((v >= k) & (seg == 2), D, y, end)
    comm = pd.read_pickle(f"{prefix}_comm_{col}.pkl")             # сделки C и их плацебо из committee.py
    assert len(comm) == len(tkC) and (comm["T"].to_numpy() == T[tkC]).all(), "сделки C не совпали с committee.py"
    X = FD[FD[col].notna() & (FD["T"] >= D0)]
    if grid_h == 4:
        X = X[X["T"] % (4 * 3600) == 0]
    X = X.sort_values(["T", "s"]).reset_index(drop=True)
    vD, _ = CM.votes(R, masks(X, specs))
    yD = X[col].to_numpy(float); eD = X["u_e_" + col[2:]].to_numpy(float); TD = X["T"].to_numpy(np.int64)
    tkD = CM.honest(vD >= k, X, yD, eD)
    plD = CM.placebo(X, tkD, col)
    mD, tD, nD = CM.ct(yD[tkD], TD[tkD])
    monD = (TD.max() + 3600 - D0) / (30.44 * DAY) if len(TD) else np.nan
    monC = (CM.C1 - bombe.TB) / (30.44 * DAY)
    yy = np.r_[comm.y.to_numpy(), yD[tkD]]; tt = np.r_[comm["T"].to_numpy(), TD[tkD]]; pp = np.r_[comm.pl.to_numpy(), plD]
    m, t, n = CM.ct(yy, tt); md, td, _ = CM.ct(yy - pp, tt)
    print(f"\n=== {prefix} {col} (сетка {grid_h} ч): правил {nP}, k {k} ===")
    print(f"  D: наблюдений {len(X)}, сделок {nD} ({nD / monD:.1f} в мес.), {mD:+.2%} (t {tD:+.1f}); "
          f"сверх плацебо {CM.ct(yD[tkD] - plD, TD[tkD])[0]:+.2%}; все наблюдения D {np.nanmean(yD):+.2%}")
    print(f"  C: сделок {len(comm)}, {comm.y.mean():+.2%}")
    print(f"  C + D: {n} сделок ({n / (monC + monD):.1f} в мес.), {m:+.2%} (t {t:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f})")
    ok = [("D > 0", mD > 0), ("C + D: t ≥ 3", m > 0 and t >= 3), ("≥ 20 в мес.", n / (monC + monD) >= 20),
          ("лучше плацебо", md > 0)]
    print("  порог D: " + "; ".join(f"{a} — {'да' if c else 'нет'}" for a, c in ok)
          + ("  → ПРОЙДЕН" if all(c for _, c in ok) else "  → не пройден"))
    pd.DataFrame({"s": X.s.values[tkD], "T": TD[tkD], "y": yD[tkD], "pl": plD, "v": vD[tkD]}).to_pickle(
        f"s224_D_{prefix}_{col}.pkl")


def main(args):
    for a in args or ["s223:y_hs4:4"]:
        prefix, col, g, *fd = a.split(":")
        os.environ["PFX"] = prefix
        check(prefix, col, int(g), pd.read_pickle(fd[0] if fd else "s224/feat_D.pkl"))


if __name__ == "__main__":
    main(sys.argv[1:])
