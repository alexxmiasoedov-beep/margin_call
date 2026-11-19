"""s179 — круглые уровни цены в лирах (спотовые пары XTRY Binance, часовые свечи s67/try1h.pkl, 10.2024–10.2026):
частота «закрытие впервые за 30 сут выше уровня» на круглой сетке и на контрольной (некруглой) той же густоты.
Только монеты с перпом Binance; оборот пары к лире за 24 ч ≥ 1 млн $ (по USDTTRY того же часа). Доходы не считаются.

Запуск: python3 -I probe_round_try.py <папка данных>
"""
import importlib.util
import os
import pickle
import sys

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("prl", os.path.join(HERE, "probe_round_levels.py"))
prl = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0], D]
spec.loader.exec_module(prl)


def main():
    T = pickle.load(open(os.path.join(D, "s67/try1h.pkl"), "rb"))
    usdt = T.get("USDTTRY")
    ut = pd.Series(usdt[:, 2], index=usdt[:, 0].astype(np.int64))
    F = pickle.load(open(os.path.join(D, "s2/fund2y.pkl"), "rb"))
    perps = set(F)
    t0, t1 = pd.Timestamp("2024-10-01", tz="UTC").timestamp(), pd.Timestamp("2026-10-19", tz="UTC").timestamp()
    rows = {}
    for pair, a in T.items():
        coin = pair[:-3]
        if coin in ("USDT", "USDC", "FDUSD", "BUSD", "TUSD", "EUR") or not any(p + coin in perps for p in ("", "1000", "1000000", "1M")):
            continue
        t = a[:, 0].astype(np.int64); qv = a[:, 1]; c = a[:, 2]
        fx = ut.reindex(t, method="nearest").values
        v24 = pd.Series(qv / fx).rolling(24, min_periods=24).sum().values
        pmax = pd.Series(c).shift(1).rolling(720, min_periods=720).max().values
        ok = (v24 >= 1e6) & (t >= t0) & (t < t1)
        for g in prl.GRIDS:
            for kind_, steps in (("круглые", prl.GRIDS[g]), ("контроль", prl.CTRL[g])):
                rf = prl.rfloor(c, steps)
                rows.setdefault(f"TRY A {g} {kind_}", []).extend((coin, int(x)) for x in t[ok & (rf > pmax)])
    for sig, lst in rows.items():
        df = pd.DataFrame(lst, columns=["coin", "t"])
        df["day"] = df.t // 86400
        df = df.drop_duplicates(["coin", "day"])
        m, med = prl.per_month(df.t.values, t0, t1)
        print(f"  {sig:28s} монето-суток {len(df):6d}, в месяц {m:6.1f} (медиана {med:.0f}), монет {df.coin.nunique()}")


if __name__ == "__main__":
    main()
