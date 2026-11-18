"""s165 — плацебо, хедж индексом альтов и кварталы для отобранных пампов (розничный памп + расхождение + без перегруженных
шортов). Запуск в папке периода с MC_K/MC_F: python3 <repo>/research/s165/robust.py <период>; сводка: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400
KR = {"2020–2022": None, "2022–2024": "/home/user/mc_oos/s119_old.pkl", "2024–2026": f"{OUT}/s49/trades.pkl"}
CUT = {"2020–2022": "2021-10-01", "2022–2024": "2023-10-01", "2024–2026": "2025-12-01"}


def selected(per):
    P = pd.read_pickle(f"{OUT}/s154_pumps_{per}.pkl"); V = pd.read_pickle(f"{OUT}/s159_{per}.pkl")[["s", "t", "f8"]]
    X = P.merge(V, on=["s", "t"], how="left"); X["t"] = X.t.astype(np.int64)
    if KR[per]:
        k = pd.read_pickle(KR[per])[["s", "t", "kr"]].copy(); k["t"] = k.t.astype(np.int64)
        X = X.merge(k.drop_duplicates(["s", "t"]), on=["s", "t"], how="left")
    else:
        X["kr"] = np.nan
    sel = ((X.share >= 0.26) | (X.kr >= 0.20)) & (X.F4 >= 0.5) & ~(X.f8 <= -0.001)
    return X[sel].copy()


def run(per):
    from common import K, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    X = selected(per); pl, hed = [], []
    for r in X.itertuples():
        i = idx_at(r.s, int(r.t))
        x = trade(r.s, i, tp=0.10, sl=0.25, hold_h=48, side=-1) if i is not None else None
        hed.append(x["net"] + mv(int(r.t), int(K[r.s]["t"][i]) + 900 + int(x["bars"]) * 900) if x else np.nan)
        w = [z["net"] for z in (trade(r.s, j, tp=0.10, sl=0.25, hold_h=48, side=-1) for j in
                                (idx_at(r.s, int(r.t) - b * DAY) for b in (45, 90, 135)) if j is not None) if z]
        pl.append(np.mean(w) if w else np.nan)
    X["pl"], X["hed"] = pl, hed
    X.to_pickle(f"{OUT}/s165_{per}.pkl")
    print(per, len(X), flush=True)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per in KR:
        X = pd.read_pickle(f"{OUT}/s165_{per}.pkl").rename(columns={"t": "te"}); A.append(X.assign(per=per))
        m, t, n = ct(X.net, X.te); mh, th, _ = ct(X.hed.dropna(), X.te[X.hed.notna()])
        dp = (X.net - X.pl).dropna(); md, td, _ = ct(dp, X.te[(X.net - X.pl).notna()])
        q = X.groupby(pd.to_datetime(X.te, unit="s").dt.to_period("Q")).net.agg(["count", "mean"])
        print(f"\n{per}: n={n} {m:+.2%} (t {t:+.1f}) | с хеджем {mh:+.2%} (t {th:+.1f}) | плацебо {X.pl.mean():+.2%}, сверх {md:+.2%} (t {td:+.1f}) | "
              f"тейков {(X.net > 0.09).mean():.0%}, стопов {(X.net < -0.2).mean():.0%}")
        print("  кварталы:", " ".join(f"{str(k)}:{v['mean']:+.1%}({int(v['count'])})" for k, v in q.iterrows()))
    A = pd.concat(A); m, t, n = ct(A.net, A.te); mh, th, _ = ct(A.hed.dropna(), A.te[A.hed.notna()])
    print(f"\nшесть лет: {n} {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
