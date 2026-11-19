"""s196 — архивные узлы сетей Cosmos SDK без ключа: список RPC из cosmos/chain-registry (GitHub), для каждого узла
/status → earliest_block_height и время. Цель — найти узлы с полной историей (tx_search и состояние на старых высотах).
Итог: /home/user/mc_data/s196/registry/nodes.json и таблица в логе."""
import json
import concurrent.futures as cf
from common196 import http, OUT

CHAINS = {"cosmoshub": "ATOM", "celestia": "TIA", "injective": "INJ", "sei": "SEI", "dydx": "DYDX", "osmosis": "OSMO",
          "akash": "AKT", "kava": "KAVA", "axelar": "AXL", "neutron": "NTRN", "dymension": "DYM", "saga": "SAGA",
          "bandchain": "BAND", "terra2": "LUNA", "terra": "LUNC", "fetchhub": "FET", "mantrachain": "OM",
          "zetachain": "ZETA", "initia": "INIT", "babylon": "BABY", "secretnetwork": "SCRT", "story": "IP",
          "irisnet": "IRIS", "evmos": "EVMOS", "cronos": "CRO", "cryptoorgchain": "CRO"}
RAW = "https://raw.githubusercontent.com/cosmos/chain-registry/master/{}/chain.json"


def status(url):
    d = http(url.rstrip("/") + "/status", timeout=20, tries=1)
    try:
        s = d["result"]["sync_info"]
        return int(s["earliest_block_height"]), s["earliest_block_time"][:19], int(s["latest_block_height"]), \
            d["result"]["node_info"]["other"].get("tx_index")
    except Exception:
        return None


def main():
    out = {}
    for ch, tk in CHAINS.items():
        cj = http(RAW.format(ch), tries=2)
        if not cj:
            print(ch, "нет chain.json", flush=True)
            continue
        rpcs = [x["address"] for x in (cj.get("apis") or {}).get("rpc", [])]
        rests = [x["address"] for x in (cj.get("apis") or {}).get("rest", [])]
        unb = None
        with cf.ThreadPoolExecutor(8) as ex:
            st = dict(zip(rpcs, ex.map(status, rpcs)))
        out[ch] = {"tk": tk, "rpc": st, "rest": rests}
        good = [(u, s) for u, s in st.items() if s]
        best = sorted(good, key=lambda x: (x[1][0] if x[1][0] > 0 else 10**12))
        print(f"{ch:15s} {tk:5s} узлов {len(rpcs):2d}, ответили {len(good):2d}; самые глубокие:", flush=True)
        for u, s in best[:3]:
            print(f"     {u[:60]:60s} earliest {s[0]:>10d} {s[1]} latest {s[2]} tx_index {s[3]}", flush=True)
    json.dump(out, open(f"{OUT}/registry/nodes.json", "w"))


if __name__ == "__main__":
    main()
