"""s177 — снимок DefiLlama yields (бесплатно: /pools и /lendBorrow; история займов /chartLendBorrow — 402, платно).
Сколько кредитных пулов, где базовая монета — перп Binance USDT-M, и займ ≥ 1 млн $; глубина бесплатной истории /chart
(поле count = дней истории). Без доходов. Запуск: python3 -I yields_snapshot.py [папка данных]
"""
import json
import os
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lend_events as L  # noqa: E402

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
L.D = D
RAW = os.path.join(D, "s177", "raw")


def main():
    P = json.load(open(os.path.join(RAW, "yields.llama.fi_pools.json")))["data"]
    LB = json.load(open(os.path.join(RAW, "yields.llama.fi_lendBorrow.json")))
    print(f"/pools: {len(P)} пулов; /lendBorrow: {len(LB)} пулов, поля: {', '.join(LB[0].keys())}")
    p = {x["pool"]: x for x in P}
    perps = L.perp_sets()["2024–2026"]
    rows = []
    for x in LB:
        q = p.get(x["pool"])
        if not q:
            continue
        sym = L.norm(q["symbol"])
        rows.append(dict(project=q["project"], chain=q["chain"], sym=sym, raw=q["symbol"],
                         bor=x.get("totalBorrowUsd") or 0, sup=x.get("totalSupplyUsd") or 0,
                         borrowable=x.get("borrowable"), days=q.get("count") or 0))
    df = pd.DataFrame(rows)
    df["native"] = [L.NATIVE.get({"BSC": "Binance", "OP Mainnet": "Optimism"}.get(c, c)) == s
                    for c, s in zip(df.chain, df.sym)]
    print(f"кредитных пулов с займом (borrowable): {int(df.borrowable.fillna(False).sum())}, проектов: {df.project.nunique()}")
    # В CDP и изолированных рынках (Sky, Liquity, LlamaLend, Frankencoin, Morpho, Fluid, Fraxlend…) символ пула в /pools —
    # залог, а займ — стейблкоин. Берём только пулы общего типа, где символ = занимаемая монета.
    pooled = L.POOLED | {"jupiter-lend", "kinetic", "evaa-protocol", "dolomite", "euler-v2", "silo-v2", "hypurrfi-pooled",
                         "neverland", "tydro", "flux-finance", "blend-pools-v2", "takara-lend", "layerbank"}
    print("проектов вне пулов общего типа (символ = залог или неясно): " +
          ", ".join(sorted(set(df.project) - pooled)[:40]))
    alt = df[df.sym.isin(perps) & ~df.sym.isin(L.STABLE | L.MAJOR) & df.project.isin(pooled)]
    for thr in (1e6, 2.5e5):
        a = alt[alt.bor >= thr]
        print(f"пулов с монетой-перпом (не стейбл, не BTC/ETH) и займом ≥ {thr / 1e6:g} млн $: {len(a)} "
              f"(монет {a.sym.nunique()}); из них «родных» для сети: {int(a.native.sum())}; "
              f"займ всего {a.bor.sum() / 1e6:.0f} млн $, не родных {a[~a.native].bor.sum() / 1e6:.0f} млн $")
        print("   не родные: " + ", ".join(f"{r.sym}({r.project}, {r.chain}) {r.bor / 1e6:.1f}"
                                         for r in a[~a.native].sort_values("bor", ascending=False).itertuples()))
    d = df[df.bor > 0].days
    first = pd.Timestamp("2026-11-19") - pd.to_timedelta(d.max(), unit="D")
    print(f"\nглубина /chart (дней истории у пулов с займом): медиана {d.median():.0f}, максимум {d.max()} "
          f"(с {first.date()}); проектов в списке нет: aave-v2 (снят), radiant (снят); compound-v2 — без займа")
    print("пример по проектам (макс. дней): " + ", ".join(
        f"{k} {v}" for k, v in df.groupby("project").days.max().sort_values(ascending=False).head(12).items()))


if __name__ == "__main__":
    main()
