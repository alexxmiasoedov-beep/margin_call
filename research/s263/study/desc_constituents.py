"""s263 — состав индексов TradFi-перпов (снимок constituents): какие поставщики и площадки, доля криптоплощадок
(сам перп Binance, Hyperliquid TradeXYZ, Aster, спот Binance) в индексе по группам.

Запуск из /home/user/mc_data: python3 -I <путь>/desc_constituents.py"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import group, load_meta  # noqa: E402

CRYPTO = {"binance_future", "binance", "hyperliquid", "aster_futures_index", "bybit", "okx"}


def main():
    f = sorted(glob.glob("s263/constituents_*.json"))[-1]
    C = json.load(open(f))
    meta = load_meta().set_index("symbol")
    rows = []
    for sym, lst in C.items():
        if not isinstance(lst, list):
            continue
        ut = meta.ut.get(sym, "CRYPTO")
        g = group(sym[:-4], ut) if ut != "CRYPTO" else "CRYPTO"
        for x in lst:
            rows.append(dict(sym=sym, grp=g, ex=x.get("exchange"), vsym=x.get("symbol"), w=float(x.get("weight", 0))))
    D = pd.DataFrame(rows)
    print(f"снимок {f}: символов {D.sym.nunique()}")
    print("\nПоставщики по группам: в скольких индексах есть и средний вес:")
    t = D.groupby(["grp", "ex"]).agg(n=("sym", "nunique"), w=("w", "mean")).reset_index()
    for g, x in t.groupby("grp"):
        tot = D[D.grp == g].sym.nunique()
        print(f"  {g:9s} ({tot:3d}): " + "; ".join(f"{r.ex} {r.n}/{tot} ср.вес {r.w:.3f}" for r in x.sort_values("n", ascending=False).itertuples()))
    cw = D[D.ex.isin(CRYPTO)].groupby("sym").w.sum()
    D2 = D.drop_duplicates("sym").set_index("sym")
    D2["crypto_w"] = cw.reindex(D2.index).fillna(0)
    print("\nДоля криптоплощадок (сам перп, Hyperliquid, Aster, спот Binance) в индексе, по группам: медиана / максимум")
    for g, x in D2.groupby("grp"):
        print(f"  {g:9s} медиана {x.crypto_w.median():.3f} максимум {x.crypto_w.max():.3f} ({x.crypto_w.idxmax()})")
    hl = D[D.ex == "hyperliquid"]
    print(f"\nИндексы с Hyperliquid (TradeXYZ HIP-3): {hl.sym.nunique()} — " +
          ", ".join(f"{r.sym[:-4]} {r.w:.2f}" for r in hl.sort_values("w", ascending=False).itertuples()))
    ast = D[D.ex == "aster_futures_index"]
    print(f"Индексы с Aster: {ast.sym.nunique()} — " + ", ".join(f"{r.sym[:-4]} {r.w:.2f}" for r in ast.itertuples()))
    # пересчёт валют
    conv = Counter()
    for v in D.vsym.dropna():
        if "uindex(" in v:
            conv[v.split("uindex(")[1].rstrip(")")] += 1
    print("Пересчёт валют в символах поставщиков:", dict(conv))


if __name__ == "__main__":
    main()
