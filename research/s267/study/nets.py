"""s267 — сети ввода Binance у криптоперпов USDT-M: сколько перпов принимает каждая сеть, для скольких она главная,
как устроен ввод (общий адрес с мемо или свой адрес клиента), открыт ли ввод, сколько стоит 0,5% обращения.

Источники (только чтение):
- перпы — снимок exchangeInfo s252 (`s252/exinfo.json`, 23.11.2026): PERPETUAL, underlyingType COIN, TRADING, USDT;
- сети ввода — свежий снимок `getNetworkCoinAll` (`/dev/shm/s267/netcoin.json`, без ключа);
- монеты CMC — свежий список data-api (`/dev/shm/s267/cmc_listing.json`, 3000 монет: обращение, цена, платформа)
  и карта `s167/cmc_map_all.json` (платформы всех монет). Монета CMC ищется по адресу контракта в любой сети ввода
  Binance, иначе по тикеру среди активных (наименьший ранг).
- главная сеть: токен — сеть его платформы CMC; монета без платформы — её собственная сеть (сеть Binance без адреса
  контракта или единственная «не общая» сеть, не ETH/BSC/BASE/ARBITRUM/OPTIMISM/MATIC/AVAXC/SOL/OPBNB); если такой нет —
  ETH, иначе BSC (так Binance принимает монеты сетей без своего ввода).

Итог: /dev/shm/s267/nets.json (по перпам), /home/user/mc_data/s267/nets_summary.json (по сетям) и таблица на экран.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s267/study/nets.py"""
import collections
import json
import re

EX = "s252/exinfo.json"
NC = "/dev/shm/s267/netcoin.json"
CMAP = "s167/cmc_map_all.json"
CLIST = "/dev/shm/s267/cmc_listing.json"
OUT = "/dev/shm/s267/nets.json"
SUMMARY = "/home/user/mc_data/s267/nets_summary.json"

PLAT = {
    "Ethereum": "ETH", "BNB Smart Chain (BEP20)": "BSC", "Solana": "SOL", "Base": "BASE", "Polygon": "MATIC",
    "Arbitrum": "ARBITRUM", "Avalanche C-Chain": "AVAXC", "Tron20": "TRX", "Tron10": "TRX", "TON": "TON",
    "Sui Network": "SUI", "Cardano": "ADA", "zkSync Era": "ZKSYNCERA", "XRP Ledger": "XRP", "Osmosis": "OSMO",
    "Aptos": "APT", "Near": "NEAR", "Optimism": "OPTIMISM", "Hedera Hashgraph": "HBAR", "Stellar": "XLM",
    "Algorand": "ALGO", "Bittensor": "TAO", "MultiversX": "EGLD", "Fantom": "FTM", "Sonic": "SONIC",
    "Starknet": "STARKNET", "Linea": "LINEA", "Scroll": "SCROLL", "Mantle": "MANTLE", "Celo": "CELO",
    "KAIA": "KAIA", "Cosmos": "ATOM", "Polkadot": "DOT", "Injective": "INJ", "Sei V2": "SEI", "Sei": "SEI",
    "Celestia": "TIA", "Berachain": "BERA", "Bera Chain": "BERA", "HyperEVM": "HYPEREVM", "Hyperliquid": "HYPE",
    "Blast": "BLAST", "Ronin": "RON", "Flow": "FLOW", "Neo N3": "NEO3", "Neo": "NEO3", "Vaulta": "EOS", "EOS": "EOS",
    "Stacks": "STX", "Kava": "KAVA", "Gnosis Chain": "GNO", "Cronos": "CRO", "Core": "CORE", "X Layer": "OKT",
    "Ordinals - BRC20": "BTC", "Unichain": "UNICHAIN", "Plasma": "PLASMA", "Monad": "MON", "World Chain": "WLD",
    "Manta Pacific": "MANTA", "Mantra": "MANTRA", "Metal": "MTL", "VeChain": "VET", "Chiliz": "CHZ2",
    "Robinhood Chain": "ROBINHOOD", "Terra Classic": "LUNC", "MegaETH": "MEGAETH", "Katana": "KATANA",
    "Hemi": "HEMI", "Plume": "PLUME",
}
SKIP = {"USDC", "USDT", "FDUSD", "USD1", "TUSD", "DAI", "XAUT", "PAXG", "BTCDOM", "DEFI", "USDE", "RLUSD", "U", "BFUSD"}
GENERIC = ["ETH", "BSC", "BASE", "ARBITRUM", "OPTIMISM", "MATIC", "AVAXC", "SOL", "OPBNB"]
DONE = {"ETH", "BSC", "SOL", "BASE", "ARBITRUM"}   # сети, уже собранные для 🐋 (s160, s249, s220, s243, s244)


def coin_of(base):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", base)
    return (m.group(2), {"1M": 10 ** 6}.get(m.group(1), int(m.group(1)) if m.group(1).isdigit() else 1)) \
        if m and not m.group(2)[0].isdigit() else (base, 1)


def norm(a):
    a = str(a or "").strip()
    return a.lower() if a.lower().startswith("0x") and len(a) == 42 else a


def main():
    ex = json.load(open(EX))["symbols"]
    perps = sorted({s["baseAsset"] for s in ex if s.get("contractType") == "PERPETUAL" and s.get("underlyingType") == "COIN"
                    and s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"})
    onboard = {s["baseAsset"]: s.get("onboardDate") for s in ex if s.get("contractType") == "PERPETUAL"
               and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING"}
    nc = {c["coin"]: c for c in json.load(open(NC))["data"]}
    cmap = {c["id"]: c for c in json.load(open(CMAP))}
    clist = {c["id"]: c for c in json.load(open(CLIST))["data"]["cryptoCurrencyList"]}
    for i, c in clist.items():           # свежий список главнее: у него актуальная платформа
        cmap[i] = {**cmap.get(i, {}), **{k: c.get(k) for k in ("id", "symbol", "name", "platform")}, "rank": c.get("cmcRank"),
                   "is_active": 1}
    by_addr, by_sym = collections.defaultdict(list), collections.defaultdict(list)
    for c in cmap.values():
        pl = c.get("platform")
        if isinstance(pl, dict) and pl.get("token_address"):
            by_addr[norm(pl["token_address"])].append(c)
        if c.get("is_active") == 1:
            by_sym[str(c.get("symbol") or "").upper()].append(c)
    rows = {}
    for b in perps:
        coin, mult = coin_of(b)
        c = nc.get(b) or nc.get(coin)
        nets = (c or {}).get("networkList") or []
        r = {"perp": b, "coin": (c or {}).get("coin") or coin, "mult": mult, "nets": {}, "onboard": onboard.get(b)}
        for n in nets:
            r["nets"][n["network"]] = {
                "contract": n.get("contractAddress") or "", "dep": bool(n.get("depositEnable")),
                "wd": bool(n.get("withdrawEnable")), "memo": bool(n.get("sameAddress")), "memo_wd": bool(n.get("memoRegex")),
                "since": int(n.get("insertTime") or 0) // 1000, "name": n.get("name"), "default": bool(n.get("isDefault"))}
        cand = []
        r["skip"] = r["coin"] in SKIP or b in SKIP
        for n in nets:
            a = norm(n.get("contractAddress"))
            if a:
                cand += [x for x in by_addr.get(a, []) if str(x.get("symbol") or "").upper() in (coin.upper(), b.upper())]
        how = "addr"
        if not cand:
            how = "sym"
            cand = sorted(by_sym.get(coin.upper(), []) or by_sym.get(r["coin"].upper(), []),
                          key=lambda x: x.get("rank") or 10 ** 9)[:1]
        cm = sorted(cand, key=lambda x: x.get("rank") or 10 ** 9)[0] if cand else None
        r["cmc"], r["cmc_how"] = (cm["id"], how) if cm else (None, None)
        li = clist.get(r["cmc"]) or {}
        q = (li.get("quotes") or [{}])[0]
        r["circ"], r["price"], r["mcap"] = li.get("circulatingSupply"), q.get("price"), q.get("marketCap")
        r["usd05"] = 0.005 * r["mcap"] if r["mcap"] else None
        pl = cm.get("platform") if cm else None
        own_native = [k for k, v in r["nets"].items() if k not in GENERIC and (k == r["coin"] or not v["contract"]
                      or re.match(r"^(0x0+|0x2::sui::SUI|uluna|uusd|core\.vaulta)$", v["contract"]))]
        r["native_net"] = own_native[0] if own_native else None
        if r["coin"] in r["nets"] and not isinstance(pl, dict):
            r["home"], r["home_kind"] = r["coin"], "native"
        elif isinstance(pl, dict):
            r["home"], r["home_kind"] = PLAT.get(pl.get("name"), "?" + str(pl.get("name"))), "token"
        else:
            own = [k for k in r["nets"] if k not in GENERIC]
            pref = [k for k in own if k.startswith(r["coin"][:3])] or own
            if pref:
                r["home"] = pref[0]
            else:
                r["home"] = next((k for k in ("ETH", "BSC") if k in r["nets"]), next(iter(r["nets"]), "нет ввода"))
            r["home_kind"] = "native" if cm else "nocmc"
        rows[b] = r
    json.dump(rows, open(OUT, "w"), ensure_ascii=False)

    agg = collections.defaultdict(lambda: {"all": 0, "dep": 0, "memo": 0, "home": 0, "home_dep": 0, "home_coins": [],
                                           "other_dep_coins": []})
    for b, r in rows.items():
        for k, v in r["nets"].items():
            a = agg[k]
            a["all"] += 1
            a["dep"] += v["dep"]
            a["memo"] += v["memo"]
            if r["skip"]:
                continue
            if r["home"] == k or r.get("native_net") == k:
                a["home"] += 1
                a["home_dep"] += v["dep"]
                a["home_coins"].append([b, v["dep"], r["mcap"], r["usd05"]])
            elif v["dep"]:
                a["other_dep_coins"].append([b, r["home"], r["mcap"]])
    nowallet = [b for b, r in rows.items() if not r["nets"]]
    blind = collections.defaultdict(list)    # перпы, которых 🐋 сейчас не видит: ввод открыт только вне собранных сетей
    for b, r in rows.items():
        dep = [k for k, v in r["nets"].items() if v["dep"]]
        if dep and not r["skip"] and not set(dep) & DONE:
            blind["+".join(sorted(dep))].append([b, r["mcap"], r["usd05"]])
    print("слепое пятно 🐋 (ввод открыт только вне ETH/BSC/SOL/BASE/ARBITRUM):", sum(len(v) for v in blind.values()), "перпов")
    for k, v in sorted(blind.items(), key=lambda x: -len(x[1])):
        print(f"  {k}: " + "; ".join(f"{x[0]} {(x[1] or 0) / 1e6:.0f}M" for x in sorted(v, key=lambda z: z[1] or 0)))
    print(f"перпов: {len(perps)}; без монеты в кошельке Binance (ввод невозможен): {len(nowallet)}")
    homes = collections.Counter(r["home"] for r in rows.values() if r["nets"])
    print("главная сеть у перпов с вводом:", homes.most_common())
    print("\nсеть | перпов | ввод открыт | общий адрес с мемо (sameAddress) | главная | главная+ввод | главные монеты (капитализация, 0,5% в $)")
    for k, a in sorted(agg.items(), key=lambda x: (-x[1]["home_dep"], -x[1]["all"])):
        if k in DONE:
            hc = f"(собрано раньше; главных {a['home_dep']})"
        else:
            hc = "; ".join(f"{x[0]}{'' if x[1] else '(закрыт)'} {(x[2] or 0) / 1e6:.0f}M/{(x[3] or 0) / 1e6:.2f}M"
                           for x in sorted(a["home_coins"], key=lambda z: z[2] or 0))
        print(f"{k} | {a['all']} | {a['dep']} | {a['memo']} | {a['home']} | {a['home_dep']} | {hc}")
    print("\nнеглавные монеты с открытым вводом в несобранных сетях:")
    for k, a in sorted(agg.items(), key=lambda x: -len(x[1]["other_dep_coins"])):
        if k not in DONE and a["other_dep_coins"]:
            print(f"  {k}: " + "; ".join(f"{x[0]}({x[1]}) {(x[2] or 0) / 1e6:.0f}M" for x in a["other_dep_coins"]))
    json.dump({"perps": len(perps), "no_wallet": nowallet, "nets": agg, "blind": blind}, open(SUMMARY, "w"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
