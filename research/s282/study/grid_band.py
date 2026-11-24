"""s282 — какая доля исполнений Г1 приходится ниже нижней границы «AI-параметров» сетки Binance Futures Grid.

AI-параметры сетки (FAQ Binance «Futures Grid Trading AI Parameters Guide»): границы по дневным свечам за 7 / 30 / 180 сут,
нижняя = MA − 3·σ. Здесь — упрощённо: MA и σ дневных закрытий (UTC) за 7 сут до суток события, уровень лимитки Г1
L = c[i−1]·(1 − X) сравнивается с MA − 3σ. Только счёт (доли событий), доходы не считаются.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s282/study/grid_band.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common282 import DAY, OUT, PER, TMP  # noqa: E402
from hyp_freq import fills, universe  # noqa: E402


def main():
    lines = []
    for per, cfg in PER.items():
        E = pd.read_pickle(f"{TMP}/ev_{per}.pkl")
        K = pickle.load(open(cfg["k"], "rb"))
        F = fills(E, -1, 1e6, U=universe(E, -1))
        below, n = 0, 0
        for s, G in F.groupby("s", observed=True):
            a = K[s]
            t = a["t"].astype(np.int64)
            live = a["qv"] > 0
            j = np.flatnonzero(((t + 900) % DAY == 0) & live)          # последняя свеча суток
            dc = pd.Series(a["c"][j].astype(float), index=(t[j] + 900) // DAY - 1)    # закрытие суток d
            ma = dc.rolling(7, min_periods=7).mean()
            sd = dc.rolling(7, min_periods=7).std(ddof=0)
            for r in G.itertuples():
                d = int(r.t // DAY) - 1                                   # последние полные сутки до события
                if d not in ma.index or not np.isfinite(ma[d]):
                    continue
                i = int(np.searchsorted(t, r.t))
                L = float(a["c"][i - 1]) * (1 - r.X)
                n += 1
                below += L < ma[d] - 3 * sd[d]
        lines.append(f"{per}: исполнений Г1 с границей {n}, лимитка ниже MA7 − 3σ7 дневных закрытий — {100 * below / max(n, 1):.0f}%")
        print(lines[-1], flush=True)
    open(f"{OUT}/grid_band.txt", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
