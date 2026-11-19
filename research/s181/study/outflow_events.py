"""s181 — события «выход собственного токена из казны ≥ 0,5% / ≥ 1% обращения за сутки» (сумма по получателям,
без перекладки между казнами, сжигания и Bancor — у Bancor «владельцы» — контракты протокола) по сети Ethereum
(treasury_out.pkl), один на перп за 7 сут; по классам «продажа видна», «раздача», «неизвестно». Только частоты."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402
import treasury_outflows as T  # noqa: E402

DAY = 86400


def main():
    X = pd.read_pickle(f"{C.OUT}/treasury_out.pkl")
    X = X[~X.protos.map(lambda s: "bancor" in s) & ~X.dst.isin(["та же казна/другая казна", "сжигание"])]
    D = X.groupby(["perp", "day"]).agg(t=("t", "min"), frac=("frac", "sum")).reset_index()
    for thr in (0.005, 0.01):
        z = T.one_per(D[D.frac >= thr], "perp", 7 * DAY)
        print(f"выход из казны ≥ {thr:.1%} за сутки (без Bancor), 1 на перп за 7 сут, в месяц: " +
              " / ".join(f"{C.month_counts(z.t, p):5.2f}" for p in C.PER) + f"  (всего {len(z)}, перпов {z.perp.nunique()})")


if __name__ == "__main__":
    main()
