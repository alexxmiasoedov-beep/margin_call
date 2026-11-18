"""s156 — доля оборота пампа у его вершины (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы — s154_pumps_<период>.pkl
(s154b). F9 — доля оборота 8 последних 15-мин свечей до входа с типичной ценой в верхней трети их диапазона. Запуск в папке
периода с MC_K: python3 <repo>/research/s156/top_volume.py <период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s154"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT = "/home/user/mc_data"
PER = ("2020–2022", "2022–2024", "2024–2026")


def run(per):
    from common import K  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    F = pd.read_pickle(f"{OUT}/s154_pumps_{per}.pkl")
    f9 = []
    for r in F.itertuples():
        i = idx_at(r.s, int(r.t)); a = K[r.s]
        if i is None or i < 8:
            f9.append(np.nan); continue
        h, l, c, q = (a[k][i - 7:i + 1].astype(float) for k in ("h", "l", "c", "qv"))
        lo, hi = l.min(), h.max()
        if hi <= lo or q.sum() <= 0:
            f9.append(np.nan); continue
        tp = (h + l + c) / 3
        f9.append(float(q[tp >= lo + 2 * (hi - lo) / 3].sum() / q.sum()))
    F["F9"] = f9
    F.to_pickle(f"{OUT}/s156_{per}.pkl")
    print(per, "пампов", len(F), "F9 медиана", round(float(np.nanmedian(f9)), 3))


def report():
    from oi_test import ct  # noqa: E402
    from pick import diff  # noqa: E402
    for per in PER:
        F = pd.read_pickle(f"{OUT}/s156_{per}.pkl").rename(columns={"t": "te"}).dropna(subset=["F9"])
        q1, q2 = F.F9.quantile([1 / 3, 2 / 3])
        top, bot = F[F.F9 >= q2], F[F.F9 <= q1]
        d, t = diff(top, bot); mt, tt, nt = ct(top.net, top.te)
        print(f"{per}: верхняя треть F9 (≥ {q2:.2f}) {nt} {mt:+.2%} (t {tt:+.1f}); нижняя (≤ {q1:.2f}) {len(bot)} {bot.net.mean():+.2%}; "
              f"разница {d:+.2%} (t {t:+.1f})")
        sp = F[F.share >= 0.26]
        if len(sp) >= 30:
            a, b = sp[sp.F9 >= q2], sp[sp.F9 <= q1]
            print(f"   спот ≥ 26%: верхняя {len(a)} {a.net.mean():+.2%}, нижняя {len(b)} {b.net.mean():+.2%}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
