"""s121 — шорт новых фьючерсов через сутки на одном периоде (правило — ВЫВОДЫ.md, записано до расчёта). Период — архив
MC_K/MC_F (s15/common); новые — первая свеча с оборотом не раньше 2 сут после начала архива и не позже 15 сут до конца.
Шорт на закрытии свечи через 24 ч после первой; тейк 30 / стоп 30 / 14 сут и 7 сут / стоп 50% (s15/common.trade).
Итог — s121_<метка>.pkl в рабочей папке. Запуск: MC_K=… MC_F=… python3 <repo>/research/s121/newlist3.py <метка>"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
from common import K, live, trade  # noqa: E402

EX = {"30/30/14": dict(tp=0.30, sl=0.30, hold_h=336), "7 сут/стоп 50": dict(tp=None, sl=0.50, hold_h=168)}
SKIP = {"BTC", "ETH", "USDC", "BUSD", "TUSD", "FDUSD", "USDP", "DAI", "USDE", "PAXG", "XAUT"}


def main():
    lab = sys.argv[1]
    g = K["BTC"]["t"]; g0, g1 = float(g[0]), float(g[-1])
    rows = []
    for s in K:
        if s in SKIP:
            continue
        lo, hi = live(s)
        if not (g0 + 2 * 86400 <= lo <= g1 - 15 * 86400):
            continue
        j = int(np.searchsorted(K[s]["t"], lo)) + 96
        d = dict(s=s, t=float(lo + 86400))
        for nm, kw in EX.items():
            x = trade(s, j, side=-1, **kw)
            d[nm] = x["net"] if x else np.nan
            if nm == "30/30/14" and x:
                d["why"] = x["why"]
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle(f"s121_{lab}.pkl")
    months = (g1 - g0) / (30.4 * 86400)
    print(f"{lab}: новых фьючерсов {len(X)} ({len(X) / months:.1f} в мес.)", end="")
    for nm in EX:
        x = X[X[nm].notna()]
        print(f" | {nm}: {x[nm].mean():+.2%} медиана {x[nm].median():+.2%} в плюсе {(x[nm] > 0).mean():.0%}", end="")
    print()


if __name__ == "__main__":
    main()
