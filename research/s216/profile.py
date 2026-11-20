"""s216 — сводка без отбора: доход шорта и лонга в нижнем и верхнем квинтиле каждого признака займа и ставки на всём периоде,
разница с t по неделям. Запуск из /home/user/mc_data: python3 <repo>/research/s216/profile.py"""
import numpy as np
import pandas as pd

LOAN = ("bor", "rep", "net", "rb", "b4", "b24", "r4x", "r24x", "bqv", "bmc", "place", "pres7", "run", "net7", "hold",
        "rate", "ux", "dr24", "lim")
OUT = ("s4", "s24", "s48", "s168", "l24")
WEEK = 7 * 86400


def main():
    D = pd.read_pickle("s216_feat.pkl")
    T = D["T"].to_numpy(np.int64)
    print("Нижний и верхний квинтиль признака на всём периоде: средний доход сделки и t разницы (по неделям)\n")
    for f in LOAN:
        x = D[f].to_numpy(float); ok = np.isfinite(x)
        if ok.sum() < 1000:
            continue
        u = np.unique(x[ok])
        if u.size <= 2:
            lo, hi = ok & (x == u[0]), ok & (x == u[-1]); lab = (f"= {u[0]:g}", f"= {u[-1]:g}")
        else:
            e = np.quantile(x[ok], [0.2, 0.8]); lo, hi = ok & (x <= e[0]), ok & (x >= e[1]); lab = (f"≤ {e[0]:.3g}", f"≥ {e[1]:.3g}")
        cells = []
        for o in OUT:
            y = D[o].to_numpy(float)
            a = lo & np.isfinite(y); b = hi & np.isfinite(y)
            ma, mb = y[a].mean(), y[b].mean()
            sa = pd.Series(y[a] - ma).groupby(T[a] // WEEK).sum() / a.sum()
            sb = pd.Series(y[b] - mb).groupby(T[b] // WEEK).sum() / b.sum()
            se = np.sqrt((sb.sub(sa, fill_value=0) ** 2).sum())
            cells.append(f"{o} {ma:+.2%} → {mb:+.2%} (t {(mb - ma) / se:+.1f})")
        print(f"{f:6s} [{lab[0]} | {lab[1]}]: " + "; ".join(cells))


if __name__ == "__main__":
    main()
