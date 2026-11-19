"""s196 — текущая очередь анбондинга всех сетей Cosmos SDK с перпом Binance (без архива): снимок «сейчас» через
rest.cosmos.directory / publicnode (без ключа), параметр unbonding_time, все unbonding_delegations валидаторов BONDED
и UNBONDING. Снимок — это календарь выхода на ближайшие unbonding_time сут (как в боте). Итог —
/home/user/mc_data/s196/cosmos/now_<сеть>.json."""
import json
import os
import sys
import cosmos_snap as cs
from common196 import http, OUT

NOW = {  # сеть: (тикер, показатель степени, REST)
    "injective": ("INJ", 18, ["https://injective-rest.publicnode.com", "https://rest.cosmos.directory/injective"]),
    "sei": ("SEI", 6, ["https://sei-rest.publicnode.com", "https://rest.cosmos.directory/sei"]),
    "dydx": ("DYDX", 18, ["https://dydx-rest.publicnode.com", "https://rest.cosmos.directory/dydx"]),
    "osmosis": ("OSMO", 6, ["https://osmosis-rest.publicnode.com", "https://rest.cosmos.directory/osmosis"]),
    "akash": ("AKT", 6, ["https://akash-rest.publicnode.com", "https://rest.cosmos.directory/akash"]),
    "axelar": ("AXL", 6, ["https://axelar-rest.publicnode.com", "https://rest.cosmos.directory/axelar"]),
    "dymension": ("DYM", 18, ["https://dymension-rest.publicnode.com", "https://rest.cosmos.directory/dymension"]),
    "saga": ("SAGA", 6, ["https://saga-rest.publicnode.com", "https://rest.cosmos.directory/saga"]),
    "bandchain": ("BAND", 6, ["https://band-rest.publicnode.com", "https://rest.cosmos.directory/bandchain"]),
    "terra2": ("LUNA", 6, ["https://terra-rest.publicnode.com", "https://rest.cosmos.directory/terra2"]),
    "terra": ("LUNC", 6, ["https://terra-classic-lcd.publicnode.com", "https://rest.cosmos.directory/terra"]),
    "fetchhub": ("FET", 18, ["https://rest-fetchhub.fetch.ai", "https://rest.cosmos.directory/fetchhub"]),
    "mantrachain": ("OM", 6, ["https://api.mantrachain.io", "https://rest.cosmos.directory/mantrachain"]),
    "zetachain": ("ZETA", 18, ["https://zetachain-rest.publicnode.com", "https://rest.cosmos.directory/zetachain"]),
    "initia": ("INIT", 6, ["https://initia-api.polkachu.com", "https://rest.cosmos.directory/initia"]),
    "babylon": ("BABY", 6, ["https://babylon-rest.publicnode.com", "https://rest.cosmos.directory/babylon"]),
    "secretnetwork": ("SCRT", 6, ["https://secretnetwork-rest.publicnode.com", "https://rest.cosmos.directory/secretnetwork"]),
    "cosmoshub": ("ATOM", 6, ["https://cosmos-rest.publicnode.com", "https://rest.cosmos.directory/cosmoshub"]),
    "celestia": ("TIA", 6, ["https://celestia-rest.publicnode.com", "https://rest.cosmos.directory/celestia"]),
    "kava": ("KAVA", 6, ["https://kava-rest.publicnode.com", "https://rest.cosmos.directory/kava"]),
}


def one(ch):
    p = f"{OUT}/cosmos/now_{ch}.json"
    if os.path.exists(p):
        return json.load(open(p))
    tk, exp, rest = NOW[ch]
    cs.CH[ch] = dict(rest=rest, exp=exp)
    par = cs.get(ch, "/cosmos/staking/v1beta1/params", None) or {}
    ut = (par.get("params") or {}).get("unbonding_time")
    lat = cs.get(ch, "/cosmos/base/tendermint/v1beta1/blocks/latest", None) or {}
    try:
        h = int(lat["block"]["header"]["height"])
        t = lat["block"]["header"]["time"][:19]
    except Exception:
        h, t = None, None
    V = cs.vals(ch, None)
    rows, bad = [], 0
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(4) as ex:
        for r, ok in ex.map(lambda v: cs.unb(ch, None, v[0]), V):
            rows += r
            bad += (not ok)
    res = {"chain": ch, "tk": tk, "exp": exp, "unbonding_time": ut, "height": h, "time": t, "n_val": len(V),
           "bad_val": bad, "bonded": sum(x[1] for x in V) / 10 ** exp, "rows": rows}
    json.dump(res, open(p, "w"))
    print(f"{ch:14s} {tk:5s} unbonding_time {ut} валидаторов {len(V)} (сбоев {bad}) записей {len(rows)} "
          f"в очереди {sum(r[5] for r in rows) / 10 ** exp:,.0f} бондинг {res['bonded']:,.0f}", flush=True)
    return res


if __name__ == "__main__":
    for ch in (sys.argv[1:] or list(NOW)):
        try:
            one(ch)
        except Exception as e:
            print(ch, "ошибка", repr(e)[:200], flush=True)
