"""s183 — охват данных по трём периодам: сколько ликвидных альтов на недельном срезе (понедельник 00:00 UTC), у скольких
есть спот Binance, рынок к воне, капитализация CMC (топ-200), OI архива; распределения признаков у ликвидных альтов.
Доходы не считаются.

Запуск: python3 -I coverage.py   (после features.py и feat_oi.py)"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402

FEATS = ["r7", "r28", "r28s", "max28", "vol28", "ivol28", "beta28", "dbeta28", "skew28", "rsj7", "abto", "sabto",
         "amihud28", "tsize7", "ntr", "tbi7", "f7", "df", "fneg7", "sshare7", "prem7", "bmom28", "kshare7", "kabn",
         "kabto", "ksabto", "kprem7", "lmcap", "turn7", "oi_g7", "oi_qv", "oi_mc", "lsr_acc", "lsr_top", "cgo60",
         "dhi90", "lprice", "age"]


def load(per):
    p = f"{C.OUT}/feat2_{per}.pkl"
    X = pd.read_pickle(p if os.path.exists(p) else f"{C.OUT}/feat_{per}.pkl")
    return X[~X.s.isin(["BTC", "ETH"])]


def main():
    out = []
    for per in C.PERS:
        X = load(per)
        nmon = X.d0.nunique()
        print(f"\n=== {per}: срезов {nmon}, месяцев {C.months(per):.1f}", flush=True)
        for thr in (2e6, 5e6, 20e6):
            g = X[(X.qv7 >= thr)].groupby("d0").size()
            print(f"  альтов с оборотом перпа ≥ {thr / 1e6:.0f} млн $ в сутки (7 сут), возраст ≥ 30 сут: медиана {g.median():.0f}, "
                  f"мин {g.min()}, макс {g.max()}")
        L = X[X.liq5.astype(bool)]
        def cnt(mask):
            g = L[mask].groupby("d0").size().reindex(L.d0.unique(), fill_value=0)
            return f"медиана {g.median():.0f} (мин {g.min()}, макс {g.max()}), доля {mask.mean():.0%}"
        print("  среди ликвидных (≥ 5 млн $):")
        print("    со спотом Binance (sshare7):", cnt(L.sshare7.notna()))
        print("    с рынком к воне (kshare7):  ", cnt(L.kshare7.notna()))
        print("    в CMC топ-200 (mcap):       ", cnt(L.mcap.notna()))
        if "oi" in L.columns:
            print("    с OI архива (oi):           ", cnt(L.oi.notna()))
            print("    с ростом OI за 7 сут:       ", cnt(L.oi_g7.notna()))
            first_oi = L[L.oi.notna()].d0.min()
            if pd.notna(first_oi):
                print("    первый срез с OI:", pd.Timestamp(int(first_oi), unit="s", tz="UTC").date())
        print("  распределения у ликвидных альтов (p5 / p25 / p50 / p75 / p95; доля непустых):")
        for f in FEATS:
            if f not in L.columns:
                continue
            v = L[f].replace([np.inf, -np.inf], np.nan).dropna()
            if not len(v):
                continue
            q = v.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).values
            print(f"    {f:9s} " + " / ".join(f"{x:+.3g}" for x in q) + f"   ({len(v) / len(L):.0%})")
            out.append((per, f, *q, len(v) / len(L)))
    pd.DataFrame(out, columns=["per", "f", "p5", "p25", "p50", "p75", "p95", "cover"]).to_pickle(f"{C.OUT}/coverage.pkl")


if __name__ == "__main__":
    main()
