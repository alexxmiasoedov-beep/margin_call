"""s220 — монеты в обращении по дням для токенов Solana с фьючерсом Binance: монета CoinMarketCap с тем же тикером и медианой
цены к фьючерсу 0,8–1,25 (как s171/k3), история CMC `cryptocurrency/historical` (кэш s171/cmc). Итог — sol_circ.json:
{фьючерс: {"cmc": id, "days": [[ГГГГ-ММ-ДД, монет в обращении, цена], …]}}. Токенизированные акции и индексы пропускаются.
Запуск из /home/user/mc_data: python3 <repo>/research/s220/circ.py"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s171", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import k3  # noqa: E402  (hist(), кэш s171/cmc)

SKIP = {"TTWO", "MU", "SPCX", "ANTHROPIC", "META", "ORDI", "ASR", "CAT"}   # акции (CAT — Caterpillar), индексы, не родные Solana
OVERRIDE = {"HOME": 36133}            # Defi App: у CMC основная сеть BNB, по цене совпадала чужая OtterHome (Arbitrum)


def main():
    import fastbt as FB  # noqa: E402
    S = [r for r in json.load(open("s220/sol_perps.json")) if not r["eth"] and r["fs"] not in SKIP]
    cmc = json.load(open("s167/cmc_map_all.json"))
    by = {}
    for c in cmc:
        by.setdefault(str(c.get("symbol") or "").upper(), []).append(c)
    out = {}
    for r in S:
        fs = r["fs"]
        if fs not in FB.K:
            continue
        coin, mult = k3.base(fs)
        a = FB.K[fs]; m = (a["qv"] > 0) & (a["t"] % 86400 == 86400 - 900)
        px = pd.Series(a["c"][m].astype(float) / mult,
                       index=pd.to_datetime(a["t"][m].astype(np.int64) // 86400 * 86400, unit="s").strftime("%Y-%m-%d"))
        best = None
        same = [c for c in by.get(coin, []) if isinstance(c.get("platform"), dict)
                and c["platform"].get("token_address") == r["mint"]]          # сначала — монета CMC с тем же адресом в Solana
        if fs in OVERRIDE:
            same = [{"id": OVERRIDE[fs]}]
        if same:
            best = (same[0]["id"], 1.0, k3.hist(same[0]["id"]))
        for c in ([] if same else by.get(coin, [])):
            h = k3.hist(c["id"])
            q = pd.Series({d: cl for d, _, cl, _ in h if cl}, dtype=float)
            j = q.index.intersection(px.index)
            if len(j) < 20:
                continue
            rr = float(np.median(q[j].values / px[j].values))
            if 0.8 <= rr <= 1.25 and (best is None or abs(np.log(rr)) < abs(np.log(best[1]))):
                best = (c["id"], rr, h)
        if best:
            out[fs] = {"cmc": best[0], "mint": r["mint"], "days": [[d, ci, cl] for d, ci, cl, _ in best[2] if ci and cl]}
        print(fs, "CMC", best[0] if best else "—", flush=True)
    json.dump(out, open("s220/sol_circ.json", "w"))
    print("готово:", len(out), "из", len(S))


if __name__ == "__main__":
    main()
