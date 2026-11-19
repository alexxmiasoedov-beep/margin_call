"""s181 — TWAP-продажи через CoW Protocol (ComposableCoW, сбор s168: work/cow_twap_ours.json — [блок, токен продажи,
токен покупки, размер части, частей, секунд на часть, владелец, tx]) — кто продаёт: казначейства DefiLlama-Adapters
(строгий список, dla_parse.py), Safe и прочие. Размер — вся заявка (часть × частей) к обращению CMC на дату.
Только частоты; доходы не считаются."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402
import treasury_outflows as T  # noqa: E402

DAY = 86400


def main():
    S = json.load(open(f"{C.D}/s160/sets.json"))
    TOK = S["toks"]
    META = json.load(open(f"{C.D}/s160/tok_meta.json"))
    dla = json.load(open(f"{C.OUT}/dla_treasury.json"))
    own = {}
    for r in dla:
        for a in r["owners"]:
            own.setdefault(a, set()).add(r["proto"])
    L = json.load(open(f"{C.D}/s168/work/cow_twap_ours.json"))
    X = pd.DataFrame(L, columns=["block", "sell", "buy", "part", "n", "sec", "owner", "tx"])
    X["sell"] = X.sell.str.lower(); X["owner"] = X.owner.str.lower()
    X = X[X.sell.isin(TOK.keys())].drop_duplicates(["owner", "sell", "part", "n", "sec"])
    X["amt"] = [p * n / 10 ** int((META.get(s) or {}).get("decimals") or 18) for p, n, s in zip(X.part, X.n, X.sell)]
    X["t"] = T.block_time()(X.block.values)
    X["frac"] = T.frac(X.rename(columns={"sell": "tok"}), T.circ_table())
    X["perp"] = X.sell.map(lambda t: TOK[t]["perp"])
    X["hours"] = X.n * X.sec / 3600
    X["treas"] = X.owner.isin(own.keys())
    print(f"TWAP-продаж токенов с перпом: {len(X)}; владельцев {X.owner.nunique()}; из них казначейств DefiLlama "
          f"{int(X.treas.sum())} ({X[X.treas].owner.nunique()} адресов)")
    for lab, y in (("все", X), ("казначейства DefiLlama", X[X.treas])):
        for thr in (0.0005, 0.005):
            z = T.one_per(y[y.frac >= thr], "perp", 7 * DAY)
            print(f"  {lab:24s} ≥ {thr:.2%}: в месяц " + " / ".join(f"{C.month_counts(z.t, p):5.2f}" for p in C.PER) +
                  f"  (всего {len(z)}; медиана длительности {z.hours.median():.0f} ч)")
    big = X[X.frac >= 0.0005]
    print("  кто продаёт ≥ 0,05% (топ владельцев):",
          big.groupby("owner").size().sort_values(ascending=False).head(10).to_dict())
    print("  монеты:", big.groupby("perp").size().sort_values(ascending=False).head(12).to_dict())
    print("  владельцы-казначейства:", {",".join(sorted(own[a])): n for a, n in big[big.treas].groupby("owner").size().items()})


if __name__ == "__main__":
    main()
