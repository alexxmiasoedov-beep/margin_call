"""s251 — 🐋 по происхождению (гипотеза — ВЫВОДЫ.md, записана до расчёта). Запуск из /home/user/mc_data:
python3 <repo>/research/s251/g2.py"""
import importlib.util
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("s221run", os.path.join(HERE, "..", "s221", "run.py"))
S221 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S221)
DAY = 86400
CALM = 0.05
MID = {"2020–2022": "2021-10-01", "2022–2024": "2023-10-01", "2024–2026": "2025-10-01"}


def groups(T, O, MM, by):
    def prof(a, t):
        g = by.get(a)
        if g is None:
            return False
        x = g[(g.t >= t - 365 * DAY) & (g.t < t)]
        return x.tok.nunique() >= 5
    J = pd.merge_asof(T.sort_values("tb"), O[["perp", "t", "frac", "src1"]].rename(columns={"t": "o_t", "frac": "o_frac"}),
                      left_on="tb", right_on="o_t", by="perp", direction="nearest", tolerance=3600)
    J.loc[(J.o_frac - J.frac).abs() > 1e-3 * J.frac.abs(), "src1"] = np.nan
    J["a"] = J.src1.isin(MM.keys())
    J["b"] = [(not a) and isinstance(s, str) and prof(s, t) for a, s, t in zip(J.a, J.src1, J.tb)]
    return J


def diff(x, mask):
    """Разница средних (в) − (а + б) по неделям: доход с хеджем, t по неделям объединённой выборки."""
    w = S221.wk(x.entry)
    d = pd.DataFrame({"w": w, "y": x.hed.values, "g": mask.values})
    m1, m0 = d[~d.g].y.mean(), d[d.g].y.mean()
    # t: остатки от средних своих групп, суммы по неделям
    r = np.where(d.g, d.y - m0, d.y - m1)
    n1, n0 = (~d.g).sum(), d.g.sum()
    wt = np.where(d.g, -1.0 / n0, 1.0 / n1) * r
    se = np.sqrt((pd.Series(wt).groupby(d.w).sum() ** 2).sum())
    return m1 - m0, (m1 - m0) / se if se > 0 else np.nan


def main():
    O = pd.read_pickle("s182_origin.pkl")
    MM = json.load(open("s250/mm_labels_eth.json"))
    W = pd.read_pickle("s207_withdrawals.pkl")
    by = {a: g for a, g in W[W.kind == "wallet"][["to", "tok", "t"]].groupby("to")}
    tot = []
    for per in ("2020–2022", "2022–2024", "2024–2026"):
        T = pd.read_pickle(f"s213_main_{per}.pkl")
        J = groups(T, O, MM, by)
        x = J[J.net.notna() & (J.r24.abs() <= CALM)].copy()
        months = len(pd.period_range(pd.to_datetime(x.entry.min(), unit="s"), pd.to_datetime(x.entry.max(), unit="s"), freq="M"))
        S221.MID = pd.Timestamp(MID[per], tz="UTC").timestamp()
        ab = x.a | x.b
        print(f"\n{per}:")
        print(f"  🐋 все: {S221.line(x, months)}")
        print(f"  (в) прочие: {S221.line(x[~ab], months)}")
        print(f"  (а + б): {S221.line(x[ab], months)}")
        print(f"  (а) ММ: {S221.line(x[x.a], months)}")
        print(f"  (б) проф.: {S221.line(x[x.b], months)}")
        d, t = diff(x, ab)
        print(f"  Δ (в) − (а + б), с хеджем: {d:+.2%} (t {t:+.1f})")
        tot.append(x.assign(per=per, ab=ab))
    A = pd.concat(tot, ignore_index=True)
    d, t = diff(A, A.ab)
    print(f"\nвместе: Δ (в) − (а + б), с хеджем: {d:+.2%} (t {t:+.1f})")
    pd.to_pickle(A, "s251_trades.pkl")


if __name__ == "__main__":
    main()
