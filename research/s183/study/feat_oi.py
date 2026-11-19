"""s183 — добавить к недельным признакам открытый интерес и позиции счетов (архив metrics, последняя 5-мин отметка
воскресенья, oi_fetch.py):
  oi_g7    — лог роста OI в монетах за 7 сут (воскресенье к воскресенью);
  oi_qv    — OI $ / средний дневной оборот перпа за 7 сут («дни оборота в позициях»);
  oi_mc    — OI $ / капитализация CMC (только монеты топ-200);
  lsr_acc  — отношение лонг/шорт всех счетов, lsr_top — топ-трейдеров по позициям, taker — buy/sell объёма тейкеров
             (последняя 5-мин отметка).
Запуск: python3 -I feat_oi.py <период>   Итог: /home/user/mc_data/s183/feat2_<период>.pkl"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402


def main(per):
    X = pd.read_pickle(f"{C.OUT}/feat_{per}.pkl")
    path = f"{C.OUT}/oi_{per}.pkl"
    O = pickle.load(open(path, "rb")) if os.path.exists(path) else {}

    def get(s, d, i):
        v = O.get((s, int(d)))
        if not v:
            return np.nan
        x = v[i]
        return x if x and np.isfinite(x) and x > 0 else np.nan
    d1 = X.d0 - C.DAY
    X["oi"] = [get(s, d, 0) for s, d in zip(X.s, d1)]
    X["oi_usd"] = [get(s, d, 1) for s, d in zip(X.s, d1)]
    X["oi_prev"] = [get(s, d - 7 * C.DAY, 0) for s, d in zip(X.s, d1)]
    X["lsr_top"] = [get(s, d, 3) for s, d in zip(X.s, d1)]
    X["lsr_acc"] = [get(s, d, 4) for s, d in zip(X.s, d1)]
    X["taker"] = [get(s, d, 5) for s, d in zip(X.s, d1)]
    X["oi_g7"] = np.log(X.oi / X.oi_prev)
    X["oi_qv"] = X.oi_usd / X.qv7
    X["oi_mc"] = X.oi_usd / X.mcap
    X.to_pickle(f"{C.OUT}/feat2_{per}.pkl")
    L = X[X.liq5.astype(bool) & ~X.s.isin(["BTC", "ETH"])]
    print(per, "ликвидных строк", len(L), "с OI", int(L.oi.notna().sum()), "с ростом OI", int(L.oi_g7.notna().sum()),
          "| срезов с OI", L[L.oi.notna()].d0.nunique(), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
