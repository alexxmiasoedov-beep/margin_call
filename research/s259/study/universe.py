"""s259 — вселенная: криптоперпы k2y, дата спота Binance, «без спота на момент», живое окно перпа, снимок индекса.
Итог — /home/user/mc_data/s259/universe.json и частоты (монето-сутки без спота по месяцам, переходы «без спота → спот»).
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/universe.py"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import DAY, T0, T1, OUT, crypto_perps, live, load_k, snapshot, spot_start  # noqa: E402


def main():
    t0 = time.time()
    K = load_k()
    print(f"k2y: {len(K)} символов, {time.time() - t0:.0f} с", flush=True)
    P = crypto_perps(K)
    ss = spot_start(P)
    SN = snapshot()
    U = {}
    for p in P:
        a = K[p]
        l0, l1 = live(a)
        if l0 is None:
            continue
        s0 = ss[p]
        U[p] = dict(live0=l0, live1=l1, spot0=s0, snap=p in SN, **({k: SN[p][k] for k in ("self", "alpha", "dex", "ext",
                                                                                           "ext_max", "n")} if p in SN else {}))
    os.makedirs(OUT, exist_ok=True)
    json.dump(U, open(f"{OUT}/universe.json", "w"))
    # монето-сутки без спота и со спотом по месяцам (в пределах k2y)
    rows = []
    for p, u in U.items():
        a0, a1 = max(u["live0"], T0), min(u["live1"], T1)
        if a1 <= a0:
            continue
        s0 = u["spot0"] if u["spot0"] else np.inf
        days = np.arange(a0 - a0 % DAY, a1, DAY)
        for d in days:
            rows.append((p, d, d < s0))
    D = pd.DataFrame(rows, columns=["p", "d", "nospot"])
    D["m"] = pd.to_datetime(D.d, unit="s").dt.strftime("%Y-%m")
    g = D.groupby(["m", "nospot"]).p.nunique().unstack(fill_value=0)
    g.columns = ["со спотом", "без спота"]
    print("перпов в месяце (живых хотя бы день):")
    print(g.to_string())
    ns = D[D.nospot]
    print(f"\nмонето-суток без спота: {len(ns)}, перпов, бывших без спота: {ns.p.nunique()}; со спотом: {len(D) - len(ns)}")
    tr = [p for p, u in U.items() if u["spot0"] and max(u["live0"], T0) < u["spot0"] < min(u["live1"], T1)]
    print(f"переходов «без спота → спот» внутри окна перпа (10.2024–10.2026): {len(tr)}")
    trd = pd.Series({p: U[p]["spot0"] for p in tr})
    print("по кварталам:", pd.to_datetime(trd, unit="s").dt.to_period("Q").value_counts().sort_index().to_dict())
    sn = [p for p in U if U[p]["snap"]]
    print(f"перпов снимка 23.11.2026 в k2y: {len(sn)} из 156; с самоссылкой (binance_future > 0): "
          f"{sum(U[p]['self'] > 0 for p in sn)}; с Alpha: {sum(U[p]['alpha'] > 0 for p in sn)}; с DEX: "
          f"{sum(U[p]['dex'] > 0 for p in sn)}")


if __name__ == "__main__":
    main()
