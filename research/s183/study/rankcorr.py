"""s183 — связи признаков без доходов: средние по срезам ранговые корреляции Спирмена между признаками у ликвидных
альтов (≥ 5 млн $ в сутки), устойчивость рангов неделя к неделе и доля поперечного разброса кандидатных признаков,
которую объясняют известные характеристики (R² недельной регрессии рангов). Доходы не считаются.

Запуск: python3 -I rankcorr.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402
from coverage import load  # noqa: E402

F = ["r7", "r28", "r28s", "max28", "vol28", "ivol28", "beta28", "dbeta28", "skew28", "rsj7", "lqv", "abto", "sabto",
     "amihud28", "tsize7", "tbi7", "f7", "df", "sshare7", "prem7", "bmom28", "kshare7", "kabn", "kabto", "kprem7",
     "lmcap", "turn7", "oi_g7", "oi_qv", "oi_mc", "lsr_acc", "cgo60", "dhi90", "lprice", "age"]
CAND = ["kshare7", "kabn", "kabto", "ksabto", "sabto", "abto", "oi_g7", "oi_qv", "oi_mc", "turn7", "sshare7", "cgo60",
        "max28", "beta28", "dbeta28", "ivol28", "df", "bmom28", "prem7", "lsr_acc"]
CTRL = ["lqv", "vol28", "r28", "r7", "max28", "beta28", "f7", "age"]


def main():
    allc = {}
    for per in C.PERS:
        X = load(per)
        X = X[X.liq5.astype(bool)].copy()
        X["lqv"] = np.log(X.qv7)
        X = X.replace([np.inf, -np.inf], np.nan)
        cols = [f for f in F if f in X.columns]
        mats, pers = [], {f: [] for f in cols + [c for c in CAND if c in X.columns and c not in cols]}
        prev = None
        r2 = {c: [] for c in CAND if c in X.columns}
        for d0, g in X.groupby("d0"):
            R = g.set_index("s")[list(dict.fromkeys(cols + list(r2)))].rank(pct=True)
            M = R[cols].corr(min_periods=20)
            mats.append(M.values)
            if prev is not None:
                common = R.index.intersection(prev.index)
                for f in pers:
                    if f in R.columns:
                        a, b = R.loc[common, f], prev.loc[common, f]
                        ok = a.notna() & b.notna()
                        if ok.sum() >= 20:
                            pers[f].append(np.corrcoef(a[ok], b[ok])[0, 1])
            prev = R
            for c in r2:                               # R² рангов признака на ранги контролей (без самого признака)
                ctr = [k for k in CTRL if k != c and k in R.columns]
                Z = R[[c] + ctr].dropna()
                if len(Z) >= 30:
                    A = np.c_[np.ones(len(Z)), Z[ctr].values]
                    y = Z[c].values
                    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
                    res = y - A @ beta
                    r2[c].append(1 - res.var() / y.var())
        Mbar = pd.DataFrame(np.nanmean(np.array(mats), axis=0), index=cols, columns=cols)
        allc[per] = Mbar
        print(f"\n=== {per}: срезов {X.d0.nunique()}, средняя ранговая корреляция признаков (Спирмен по срезам)")
        pairs = []
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                pairs.append((a, b, Mbar.loc[a, b]))
        pairs.sort(key=lambda x: -abs(x[2]) if np.isfinite(x[2]) else 0)
        print("  сильнейшие пары |ρ| ≥ 0,4:")
        for a, b, v in pairs:
            if np.isfinite(v) and abs(v) >= 0.4:
                print(f"    {a:8s} ~ {b:8s} {v:+.2f}")
        print("  кандидаты против ключевых признаков (ρ):")
        keys = ["r7", "r28", "max28", "vol28", "beta28", "lqv", "abto", "f7", "sshare7", "kshare7", "oi_g7", "lmcap"]
        keys = [k for k in keys if k in cols]
        print("    " + " " * 9 + " ".join(f"{k:>7s}" for k in keys))
        for c in CAND:
            if c in cols:
                print(f"    {c:9s}" + " ".join(f"{Mbar.loc[c, k]:+7.2f}" if np.isfinite(Mbar.loc[c, k]) else "      —" for k in keys))
        print("  устойчивость рангов неделя к неделе (корреляция рангов t и t−1) и R² рангов на контроли "
              f"({', '.join(CTRL)}):")
        for c in CAND:
            if c in pers and pers[c]:
                print(f"    {c:9s} устойчивость {np.mean(pers[c]):+.2f}   R² на контроли "
                      f"{np.mean(r2[c]) if r2.get(c) else float('nan'):.2f}")
    pd.to_pickle(allc, f"{C.OUT}/rankcorr.pkl")


if __name__ == "__main__":
    main()
