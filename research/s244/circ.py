"""s244 — монеты в обращении по дням для токенов Arbitrum с фьючерсом Binance (как s220/circ.py): монета CoinMarketCap с тем же
адресом в Arbitrum, иначе с тем же тикером и медианой цены к фьючерсу 0,8–1,25; история CMC `cryptocurrency/historical`
(кэш s171/cmc; до 15.01.2025 — s249/cmcfull). Итог — s244/arb_circ.json: {фьючерс: {"cmc": id, "addr": адрес в Base, "days": [[день, в обращении, цена]]}}.
Запуск из /home/user/mc_data: python3 <repo>/research/s243/circ.py"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s171", "s187", "s249"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import k3  # noqa: E402
from cmcfull import full  # noqa: E402  (история CMC до 15.01.2025, s249)

OVERRIDE = {"APE": 18876}            # у CMC «APE» по тикеру — другая монета без истории; ApeCoin — 18876
SKIP = {"ETH", "USDC", "USDT"}


def main():
    import fastbt as FB  # noqa: E402
    nets = json.load(open("s242/perp_nets.json"))
    cmc = json.load(open("s167/cmc_map_all.json"))
    by, by_addr = {}, {}
    for c in cmc:
        by.setdefault(str(c.get("symbol") or "").upper(), []).append(c)
        pl = c.get("platform") if isinstance(c.get("platform"), dict) else {}
        if pl.get("token_address"):
            by_addr[str(pl["token_address"]).lower()] = c
    out = {}
    for coin, addr, eth, bsc, ins in nets["ARBITRUM"]:
        if coin in SKIP or not addr:
            continue
        fs = next((f for f in (coin, "1000" + coin, "1000000" + coin) if f in FB.K), None)
        if not fs:
            print(coin, "нет свечей фьючерса"); continue
        c0, mult = k3.base(fs)
        a = FB.K[fs]; m = (a["qv"] > 0) & (a["t"] % 86400 == 86400 - 900)
        px = pd.Series(a["c"][m].astype(float) / mult,
                       index=pd.to_datetime(a["t"][m].astype(np.int64) // 86400 * 86400, unit="s").strftime("%Y-%m-%d"))
        best = None
        same = by_addr.get(addr.lower())
        if coin in OVERRIDE:
            same = {"id": OVERRIDE[coin]}
        if same:
            best = (same["id"], 1.0, k3.hist(same["id"]))
        for c in ([] if same else by.get(coin, [])):
            h = k3.hist(c["id"])
            q = pd.Series({d: cl for d, _, cl, _ in h if cl}, dtype=float)
            j = q.index.intersection(px.index)
            if len(j) < 20:
                continue
            rr = float(np.median(q[j].values / px[j].values))
            if sum(1 for _, ci, _, _ in h if ci) >= 30 and 0.8 <= rr <= 1.25 and (best is None or abs(np.log(rr)) < abs(np.log(best[1]))):
                best = (c["id"], rr, h)
        if best:
            out[fs] = {"cmc": best[0], "addr": addr.lower(), "eth": bool(eth), "ins": ins,
                       "days": [[d, ci, cl] for d, ci, cl, _ in full(best[0], best[2]) if ci and cl]}
        print(fs, "CMC", best[0] if best else "—", "по адресу" if same else "", flush=True)
    json.dump(out, open("s244/arb_circ.json", "w"))
    print("готово:", len(out))


if __name__ == "__main__":
    main()
