"""s249 — монеты в обращении по дням для токенов фьючерсов Binance, которые Binance принимает в BNB Chain: адрес BEP-20 —
из сетей ввода Binance (снимок s242/netcoin.json), монета CoinMarketCap — с тем же адресом в BNB Chain, иначе с тем же
тикером и медианой цены к фьючерсу 0,8–1,25 (как s220), история CMC `cryptocurrency/historical` (кэш s171/cmc — с 15.01.2025,
раньше — дозагрузка 15.08.2024–15.01.2025 в кэш s249/cmc_early).
Итог — s249/bsc_circ.json: {фьючерс: {"cmc": id, "contract": адрес, "eth": есть ли у Binance сеть ETH, "sol": есть ли SOL,
"since": время добавления сети BSC, "days": [[ГГГГ-ММ-ДД, монет в обращении, цена], …]}}.
Запуск из /home/user/mc_data: python3 <repo>/research/s249/circ.py"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s171", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
sys.path.insert(0, HERE)
import k3  # noqa: E402  (hist(), base(), кэш s171/cmc)
from cmcfull import full  # noqa: E402  (история до 15.01.2025)

SKIP = {"USDC", "FDUSD", "USD1", "TUSD", "DAI", "XAUT", "PAXG", "BTCDOM", "DEFI", "BNB", "BTC", "ETH"}   # стейблкоины, металлы,
                                                                     # индексы и монеты, которые Binance держит как резерв в BNB Chain


def universe():
    nc = json.load(open("s242/netcoin.json"))["data"]
    net = {c["coin"]: {n["network"]: n for n in c.get("networkList") or []} for c in nc}
    out = {}
    for fs in json.load(open("s220/perps.json")):
        coin, _ = k3.base(fs)
        v = net.get(fs) or net.get(coin)
        if not v or "BSC" not in v or fs in SKIP or coin in SKIP:
            continue
        a = str(v["BSC"].get("contractAddress") or "").lower()
        if not a.startswith("0x") or len(a) != 42:
            continue
        out[fs] = {"contract": a, "eth": "ETH" in v, "sol": "SOL" in v, "since": int(v["BSC"].get("insertTime") or 0) // 1000}
    return out


def main():
    import fastbt as FB  # noqa: E402
    U = universe()
    cmc = json.load(open("s167/cmc_map_all.json"))
    by = {}
    for c in cmc:
        by.setdefault(str(c.get("symbol") or "").upper(), []).append(c)
    out = {}
    for fs, r in sorted(U.items()):
        if fs not in FB.K:
            continue
        coin, mult = k3.base(fs)
        a = FB.K[fs]; m = (a["qv"] > 0) & (a["t"] % 86400 == 86400 - 900)
        px = pd.Series(a["c"][m].astype(float) / mult,
                       index=pd.to_datetime(a["t"][m].astype(np.int64) // 86400 * 86400, unit="s").strftime("%Y-%m-%d"))
        same = [c for c in by.get(coin, []) if isinstance(c.get("platform"), dict)
                and str(c["platform"].get("token_address") or "").lower() == r["contract"]]   # тот же адрес в BNB Chain
        best = (same[0]["id"], 1.0, k3.hist(same[0]["id"])) if same else None
        for c in ([] if same else by.get(coin, [])):
            h = k3.hist(c["id"])
            q = pd.Series({d: cl for d, _, cl, _ in h if cl}, dtype=float)
            j = q.index.intersection(px.index)
            if len(j) < 30:
                continue
            rr = float(np.median(q[j].values / px[j].values))
            if 0.8 <= rr <= 1.25 and (best is None or abs(np.log(rr)) < abs(np.log(best[1]))):
                best = (c["id"], rr, h)
        if best:
            out[fs] = dict(r, cmc=best[0], days=[[d, ci, cl] for d, ci, cl, _ in full(best[0], best[2]) if ci and cl])
        print(fs, "CMC", best[0] if best else "—", flush=True)
    os.makedirs("s249", exist_ok=True)
    json.dump(out, open("s249/bsc_circ.json", "w"))
    print("готово:", len(out), "из", len(U))


if __name__ == "__main__":
    main()
