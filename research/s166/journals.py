"""s166 — фильтры s165 (расхождение F4 и фандинг > −0,1%) на сделках ⏰ (три периода), 🔝 и 👀 (2024–2026). Признак F4 —
s154/feat.features (свечи периода через MC_K), фандинг — s15/common.funding. Запуск в папке периода с MC_K/MC_F:
python3 <repo>/research/s166/journals.py <период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s154", "s157"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT = "/home/user/mc_data"
O9 = {"2020–2022": "s88/oos2020_trades.pkl", "2022–2024": "s88/oos_trades.pkl", "2024–2026": "s88/trades.pkl"}


def f8_at(fr, t):
    if not len(fr):
        return np.nan
    k = int(np.searchsorted(fr[:, 0], t, "right")) - 1
    if k < 1:
        return np.nan
    iv = fr[k, 0] - fr[k - 1, 0]
    return float(fr[k, 1]) * 8 * 3600 / iv if 3600 - 60 <= iv <= 8 * 3600 + 60 else np.nan


def run(per):
    import feat  # noqa: E402
    from common import funding  # noqa: E402
    sets = []
    O = pd.read_pickle(f"{OUT}/{O9[per]}"); O = O[O.open9 & (O.share >= 0.2) & (O.r1 >= 0.05)]
    sets.append(("⏰", O.s, O.t, O.S_10_25))
    if per == "2024–2026":
        T = pd.read_pickle(f"{OUT}/s65/trades.pkl"); sets.append(("🔝", T.s, T.t, T.S_10_25))
        R = pd.read_pickle(f"{OUT}/s83/trades.pkl"); sets.append(("👀", R.s, R.t, R.S_10_25))
    rows = []
    for j, S, Tt, N in sets:
        for s, t, net in zip(S, Tt, N):
            if pd.isna(net):
                continue
            if s not in feat.K and s.endswith("USDT"):          # в старых выгрузках s88 тикер с «USDT»
                s = s[:-4]
            if s not in feat.K:
                continue
            f = feat.features(s, int(t))
            if not f:
                continue
            rows.append(dict(j=j, s=s, te=int(t), net=float(net), F4=f["F4"], f8=f8_at(funding(s), int(t))))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s166_{per}.pkl")
    print(per, X.groupby("j").size().to_dict(), flush=True)


def report():
    from oi_test import ct  # noqa: E402
    from opt_test import wdiff  # noqa: E402
    A = []
    for per in O9:
        X = pd.read_pickle(f"{OUT}/s166_{per}.pkl"); X["per"] = per; A.append(X)
    A = pd.concat(A, ignore_index=True)
    A["sel"] = (A.F4 >= 0.5) & ~(A.f8 <= -0.001)
    for j, X in A.groupby("j"):
        print(f"\n{j}:")
        for per, x in X.groupby("per"):
            a, b = x[x.sel], x[~x.sel]; d, t = wdiff(a, b); m, tt, n = ct(a.net, a.te)
            print(f"  {per}: с условиями {n} {m:+.2%} (t {tt:+.1f}) | остальные {len(b)} {b.net.mean():+.2%} | разница {d:+.2%} (t {t:+.1f})")
        a, b = X[X.sel], X[~X.sel]; d, t = wdiff(a, b); m, tt, n = ct(a.net, a.te)
        print(f"  всего: с условиями {n} {m:+.2%} (t {tt:+.1f}) | остальные {b.net.mean():+.2%} | разница {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
