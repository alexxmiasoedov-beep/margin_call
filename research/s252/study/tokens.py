"""s252 — сеть и адрес токена у перпов без спота Binance (nospot.json).
Источники по порядку: список Binance Alpha (`bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list`, сеть
и контракт), сети ввода Binance (снимок s242/netcoin.json), CoinGecko `coins/list?include_platform=true` (s220/cg_list.json).
Родной токен или обёртка: монета CoinGecko с тем же тикером, id не `binance-peg-…`, у которой в платформах есть этот адрес;
обёртки Binance-Peg — id `binance-peg-…` с этим адресом. Несколько сетей у одной монеты CoinGecko — мультисетевой токен
(OFT и т. п.), пишем все.
Итог — /home/user/mc_data/s252/tokens.json: {перп: {coin, alpha_chain, alpha_contract, alpha_listing, bn_nets{сеть: адрес},
cg: [{id, platforms}], bsc, bsc_native, peg, chains}}.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/tokens.py"""
import collections
import json

R = json.load(open("s252/nospot.json"))
AL = json.load(open("s252/alpha_tokens.json"))["data"]
NC = json.load(open("s242/netcoin.json"))["data"]
CG = json.load(open("s220/cg_list.json"))

CHAIN = {"56": "bsc", "1": "eth", "8453": "base", "CT_501": "sol", "42161": "arb", "CT_784": "sui", "146": "sonic",
         "CT_195": "tron", "59144": "linea", "4663": "robinhood"}
CGP = {"binance-smart-chain": "bsc", "ethereum": "eth", "base": "base", "solana": "sol", "arbitrum-one": "arb",
       "sui": "sui", "avalanche": "avax", "polygon-pos": "polygon", "optimistic-ethereum": "op", "tron": "tron",
       "sonic": "sonic", "hyperevm": "hyperevm", "berachain": "bera", "linea": "linea", "mantle": "mantle",
       "zksync": "zksync", "aptos": "aptos", "ton": "ton", "near-protocol": "near", "plasma": "plasma",
       "world-chain": "world", "unichain": "unichain", "abstract": "abstract", "story": "story", "monad": "monad",
       "megaeth": "megaeth"}
NCN = {"BSC": "bsc", "ETH": "eth", "BASE": "base", "SOL": "sol", "ARBITRUM": "arb", "AVAXC": "avax", "MATIC": "polygon",
       "OPTIMISM": "op", "SUI": "sui", "TRX": "tron", "APT": "aptos", "TON": "ton", "SONIC": "sonic", "BERA": "bera"}

al_by = collections.defaultdict(list)
for a in AL:
    al_by[str(a.get("symbol") or "").upper()].append(a)
    if a.get("cexCoinName"):
        al_by[str(a["cexCoinName"]).upper()].append(a)
nc_by = {c["coin"]: c for c in NC}
cg_by = collections.defaultdict(list)
cg_addr = collections.defaultdict(list)
for c in CG:
    cg_by[str(c.get("symbol") or "").upper()].append(c)
    for p, a in (c.get("platforms") or {}).items():
        if a:
            cg_addr[str(a).lower()].append(c)

out = {}
for s, v in R.items():
    coin = v["coin"]
    r = {"coin": coin, "base": v["base"]}
    al = [a for a in al_by.get(coin.upper(), []) + al_by.get(v["base"].upper(), [])]
    al = list({a["tokenId"]: a for a in al}.values())
    # из нескольких Alpha-токенов с тем же тикером — с наибольшим оборотом
    al.sort(key=lambda a: -float(a.get("volume24h") or 0))
    if al:
        a = al[0]
        r.update(alpha_chain=CHAIN.get(str(a["chainId"]), str(a["chainId"])), alpha_contract=str(a["contractAddress"]),
                 alpha_listing=a.get("listingTime"), alpha_id=a.get("alphaId"), alpha_n=len(al),
                 alpha_circ=a.get("circulatingSupply"), alpha_offline=a.get("offline"))
    nc = nc_by.get(v["base"]) or nc_by.get(coin)
    r["bn_nets"] = {NCN.get(n["network"], n["network"]): {"addr": str(n.get("contractAddress") or ""),
                                                           "dep": n.get("depositEnable"), "since": n.get("insertTime")}
                    for n in (nc or {}).get("networkList") or []}
    # CoinGecko: по адресу Alpha / ввода Binance, иначе по тикеру
    addrs = {str(r.get("alpha_contract") or "").lower()} | {x["addr"].lower() for x in r["bn_nets"].values()}
    addrs.discard("")
    cgs = {}
    for a in addrs:
        for c in cg_addr.get(a, []):
            cgs[c["id"]] = c
    if not cgs:
        for c in cg_by.get(coin.upper(), []):
            cgs[c["id"]] = c
    r["cg"] = [{"id": c["id"], "name": c.get("name"),
                "platforms": {CGP.get(p, p): str(a).lower() for p, a in (c.get("platforms") or {}).items() if a}}
               for c in cgs.values()]
    # адрес в BNB Chain и родной ли он
    bsc = None
    if r.get("alpha_chain") == "bsc":
        bsc = r["alpha_contract"].lower()
    elif "bsc" in r["bn_nets"] and r["bn_nets"]["bsc"]["addr"].startswith("0x"):
        bsc = r["bn_nets"]["bsc"]["addr"].lower()
    else:
        own = [c for c in r["cg"] if not c["id"].startswith("binance-peg") and c["platforms"].get("bsc")]
        if len(own) == 1:
            bsc = own[0]["platforms"]["bsc"]
    r["bsc"] = bsc
    peg = [c["id"] for c in r["cg"] if c["id"].startswith("binance-peg") and bsc and c["platforms"].get("bsc") == bsc]
    native = [c["id"] for c in r["cg"] if not c["id"].startswith("binance-peg") and bsc and c["platforms"].get("bsc") == bsc]
    r["peg"] = peg
    r["bsc_native"] = bool(native) and not peg
    chains = set()
    for c in r["cg"]:
        if c["id"].startswith("binance-peg"):
            continue
        if bsc and c["platforms"].get("bsc") != bsc and r["cg"] and native:
            continue
        chains |= set(c["platforms"])
    if r.get("alpha_chain"):
        chains.add(r["alpha_chain"])
    r["chains"] = sorted(chains)
    out[s] = r
json.dump(out, open("s252/tokens.json", "w"), ensure_ascii=False, indent=0)

# сводка
pri = collections.Counter()
for s, r in out.items():
    pri[r.get("alpha_chain") or ("bsc" if r["bsc"] else (sorted(r["chains"])[0] if r["chains"] else "нет данных"))] += 1
print("перпов без спота:", len(out))
print("основная сеть (Alpha, иначе BNB Chain по CoinGecko/вводу Binance, иначе первая из CoinGecko):", pri.most_common())
print("с адресом в BNB Chain:", sum(1 for r in out.values() if r["bsc"]),
      "| родной (монета CoinGecko с этим адресом, не binance-peg):", sum(1 for r in out.values() if r["bsc_native"]),
      "| Binance-Peg:", sum(1 for r in out.values() if r["peg"]))
print("с сетью ввода Binance (любой):", sum(1 for r in out.values() if r["bn_nets"]),
      "| с вводом в BNB Chain:", sum(1 for r in out.values() if "bsc" in r["bn_nets"]))
multi = [s for s, r in out.items() if r["bsc"] and len([c for c in r["chains"] if c != "bsc"]) > 0]
print("с BNB Chain и ещё сетями (мультисетевые):", len(multi))
nob = [s for s, r in out.items() if r["bsc"] and not r["bsc_native"]]
print("адрес в BNB Chain без подтверждения CoinGecko:", nob)
