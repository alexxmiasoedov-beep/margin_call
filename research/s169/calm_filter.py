"""s169 — метка «спокойный рынок» (ход фьючерса за 24 ч до входа −5…+5%) на шортах 🔑⁺ перед разлоком (s142_<период>.pkl;
гипотеза — ВЫВОДЫ.md, записана до расчёта). Запуск в папке периода с MC_K/MC_F/MC_CUT: python3 <repo>/research/s169/calm_filter.py
<период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s157"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400
PER = ("2020–2022", "2022–2024", "2024–2026")


def run(per):
    from common import K  # noqa: E402
    U = pd.read_pickle(f"{OUT}/s142_{per}.pkl").copy()
    r24 = []
    for r in U.itertuples():
        if r.s not in K:
            r24.append(np.nan); continue
        t, c = K[r.s]["t"].astype(np.int64) + 900, K[r.s]["c"].astype(float)
        te = int(r.t)
        i = int(np.searchsorted(t, te, "right")) - 1; j = int(np.searchsorted(t, te - DAY, "right")) - 1
        r24.append(c[i] / c[j] - 1 if i >= 0 and j >= 0 and abs(t[i] - te) <= 900 and abs(t[j] - te + DAY) <= 900 else np.nan)
    U["r24"] = r24
    U.to_pickle(f"{OUT}/s169_{per}.pkl")
    print(per, len(U), "с ходом", int(U.r24.notna().sum()), flush=True)


def report():
    from opt_test import wdiff  # noqa: E402
    from oi_test import ct  # noqa: E402
    A = []
    for per in PER:
        X = pd.read_pickle(f"{OUT}/s169_{per}.pkl").dropna(subset=["r24", "net"]); X["per"] = per; A.append(X)
        a, b = X[X.r24.abs() <= 0.05], X[X.r24.abs() > 0.05]
        d, t = wdiff(a.assign(te=a.t), b.assign(te=b.t))
        m, tm, n = ct(a.net, a.t)
        print(f"{per}: спокойный рынок n={n} {m:+.2%} (t {tm:+.1f}) | прочие n={len(b)} {b.net.mean():+.2%} | разница {d:+.2%} (t {t:+.1f}) | "
              f"с хеджем {a.hed.mean():+.2%} против {b.hed.mean():+.2%}")
    A = pd.concat(A, ignore_index=True)
    a, b = A[A.r24.abs() <= 0.05], A[A.r24.abs() > 0.05]
    d, t = wdiff(a.assign(te=a.t), b.assign(te=b.t))
    print(f"вместе: спокойный рынок {len(a)} {a.net.mean():+.2%} | прочие {len(b)} {b.net.mean():+.2%} | разница {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
