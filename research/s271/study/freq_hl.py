"""s271 Г6 — оценка частоты для «уровней ликвидации крупных позиций Hyperliquid»: истории позиций без ключа нет, поэтому
частота оценивается сверху по суточным ликвидациям Hyperliquid по монете (s209: CloudFront-статистика HL, 13.06.2023 –
03.04.2026): монето-сутки, где на HL ликвидировано ≥ 1 / 5 млн $ и ≥ 2% суточного оборота перпа Binance той же монеты,
у монет с перпом Binance (без BTC и ETH). Доходы не считаются. Запуск из /home/user/mc_data."""
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import DAY, MONTH, PER, base, crypto_perps, load_k, ts  # noqa: E402


def main():
    d = json.load(gzip.open("s209/hl/daily_notional_liquidated_by_coin.json.gz"))["chart_data"]
    X = pd.DataFrame(d)
    X["t"] = (pd.to_datetime(X["time"]) - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
    X = X.rename(columns={"daily_notional_liquidated": "liq"})
    out = {}
    for per in PER:
        K = load_k(per)
        P = crypto_perps(K)
        bmap = {}
        for p in P:
            bmap.setdefault(base(p), p)
            bmap.setdefault(p, p)
        dv = {}
        for p in P:
            a = K[p]
            day = (a["t"].astype(np.int64) // DAY) * DAY
            dv[p] = pd.Series(a["qv"].astype(float)).groupby(day).sum()
        cfg = PER[per]
        Y = X[(X.t >= cfg["t0"]) & (X.t < min(cfg["t1"], ts("2026-04-04")))].copy()
        Y["p"] = [bmap.get(c.replace("k", "1000", 1) if c.startswith("k") else c) for c in Y.coin]
        Y = Y[Y.p.notna() & ~Y.p.isin(["BTC", "ETH"])]
        Y["bv"] = [float(dv[p].get(t, np.nan)) for p, t in zip(Y.p, Y.t)]
        span = (min(cfg["t1"], ts("2026-04-04")) - max(cfg["t0"], int(X.t.min()))) / MONTH
        for thr in (1e6, 5e6):
            m = (Y.liq >= thr) & (Y.liq >= 0.02 * Y.bv)
            out[(per, thr)] = (m.sum(), m.sum() / span, Y[m].p.nunique())
            print(f"{per}: ликвидации HL ≥ {thr / 1e6:.0f} млн $ и ≥ 2% оборота Binance — {m.sum()} монето-суток, "
                  f"{m.sum() / span:.1f} в мес., монет {Y[m].p.nunique()} (окно {span:.1f} мес.)")


if __name__ == "__main__":
    main()
