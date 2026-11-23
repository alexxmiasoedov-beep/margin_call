"""s259 — проверка смены формулы фандинга 18.09.2025 (объявление Binance: F = [P̄ + clamp(i − P̄, ±0,05%)] / (8/N)):
наклон ставки начисления к средней премии за интервал (15-мин закрытия premiumIndexKlines, s12/prem.pkl) до и после
по интервалам 1, 4 и 8 ч; только начисления с |P̄| ≥ 0,1% (вне зажима процентной части). Доходы не считаются.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/fund_formula.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import OUT, TMP  # noqa: E402

CH = int(pd.Timestamp("2025-09-18 08:00", tz="UTC").timestamp())


def main():
    D = pd.read_pickle(f"{TMP}/funding_panel.pkl")
    PR = pickle.load(open("s12/prem.pkl", "rb"))
    rows = []
    for s, g in D.groupby("s"):
        if s not in PR:
            continue
        pt, pv = PR[s]
        cs = np.r_[0.0, np.cumsum(pv.astype(float))]
        T = g.t.values.astype(np.int64); h = g.h.values
        a = np.searchsorted(pt, T - (h * 3600).astype(np.int64))      # свечи [T − h, T)
        b = np.searchsorted(pt, T)
        n = b - a
        ok = n >= np.maximum(h * 4 * 0.9, 1)
        pbar = np.where(ok, (cs[b] - cs[a]) / np.maximum(n, 1), np.nan)
        rows.append(pd.DataFrame({"s": s, "t": T, "h": h, "r": g.r.values, "pbar": pbar, "ns": g.ns.values}))
    X = pd.concat(rows).dropna()
    X = X[np.abs(X.pbar) >= 0.001]
    for hh in (1, 4, 8):
        for nm, m in (("до 18.09.2025", X.t < CH - 86400), ("после", X.t >= CH + 86400)):
            x = X[(X.h == hh) & m]
            if len(x) < 30:
                print(f"интервал {hh} ч, {nm}: мало ({len(x)})"); continue
            k = np.polyfit(x.pbar, x.r, 1)[0]
            ratio = (x.r / x.pbar).median()
            print(f"интервал {hh} ч, {nm}: начислений {len(x):,}; наклон ставки к средней премии {k:.2f}, медиана r/P̄ {ratio:.2f}")


if __name__ == "__main__":
    main()
