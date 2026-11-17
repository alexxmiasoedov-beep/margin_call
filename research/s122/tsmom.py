"""s122 — временной моментум на 20 самых торгуемых фьючерсах (правило — ВЫВОДЫ.md, записано до расчёта). Каждый понедельник
00:00 UTC: знак хода за 28 сут → лонг или шорт на 7 сут, стоп 15% (s15/common.trade). Сравнение — «всегда лонг» и «всегда
шорт» тех же монет. Период — архив MC_K/MC_F. Итог — s122_<метка>.pkl. Запуск: python3 <repo>/research/s122/tsmom.py <метка>"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s105"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from jumps_test import SKIP as SK  # noqa: E402

SKIP = (SK - {"BTC", "ETH"}) | {"USDC", "BUSD", "TUSD", "FDUSD", "USDP", "DAI", "PAXG", "XAUT", "BTCDOM", "DEFI"}


def main():
    lab = sys.argv[1]
    g = K["BTC"]["t"]; close = g + 900
    first = pd.Timestamp(int(close[0] + 61 * 86400), unit="s").normalize()
    mondays = [int(d.timestamp()) for d in pd.date_range(first, pd.Timestamp(int(close[-1] - 8 * 86400), unit="s"), freq="W-MON")]
    syms = [s for s in K if s not in SKIP and len(K[s]["t"]) == len(g)]
    rows = []
    for Mt in mondays:
        i = int(np.searchsorted(close, Mt))
        if i >= len(g) or close[i] != Mt:
            continue
        cand = []
        for s in syms:
            lo, hi = live(s)
            if lo > Mt - 60 * 86400 or hi < Mt + 8 * 86400:
                continue
            v30 = float(K[s]["qv"][i - 30 * 96 + 1:i + 1].sum())
            cand.append((v30, s))
        cand.sort(reverse=True)
        for v30, s in cand[:20]:
            c = K[s]["c"]
            r28 = float(c[i] / c[i - 28 * 96] - 1)
            side = 1 if r28 > 0 else -1
            x = trade(s, i, tp=None, sl=0.15, hold_h=168, side=side)
            L = trade(s, i, tp=None, sl=0.15, hold_h=168, side=1)
            S = trade(s, i, tp=None, sl=0.15, hold_h=168, side=-1)
            if x and L and S:
                rows.append(dict(t=float(Mt), s=s, side=side, r28=r28, net=x["net"], fund=x["fund"], L=L["net"], S=S["net"]))
    X = pd.DataFrame(rows)
    X.to_pickle(f"s122_{lab}.pkl")
    print(lab, "сделок", len(X), "недель", X.t.nunique())


if __name__ == "__main__":
    main()
