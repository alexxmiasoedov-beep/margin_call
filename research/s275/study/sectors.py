"""s275 — таблица «перп → сектор и экосистема» для криптоперпов Binance USDT-M (изучение; доходы не считаются).

Источники (без ключей, User-Agent "research-script/1.0", паузы между запросами):
- Binance фьючерсы `fapi/v1/exchangeInfo` (через www.binance.com): поле `underlyingSubType` — сектор, который Binance
  сам показывает у перпа (DeFi, AI, Layer-1, Meme, …). Снятые перпы в нём не видны.
- Binance сайт: `bapi/composite/v1/public/marketing/symbol/list` (теги спота и `cmcUniqueId` — точная связь с CMC)
  и `bapi/asset/v2/public/asset-service/product/get-products` (теги спотовых пар).
- CoinMarketCap data-api `cryptocurrency/listing` (aux=tags,platform): теги секторов и экосистем, сеть токена.
- CoinGecko `coins/markets?category=…` по списку категорий (лимит запросов низкий — пауза 13 с; при 429 — 70 с).

Связь перпа с монетой: тикер без множителя 1000/1M (`common259.base`); CMC — по `cmcUniqueId` Binance, иначе
по тикеру с наибольшей капитализацией и проверкой цены перпа к цене CMC (0,8–1,25), иначе «по тикеру».
CoinGecko — по тикеру и совпадению имени или капитализации с CMC (±40%).

Сектор (одно значение) — по первому сработавшему правилу:
  1) тег Binance `underlyingSubType` перпа (без служебных Crypto / Alpha / USDC / Pre-Market / Cross Pair);
  2) теги CMC по списку приоритетов `CMC2SEC`;
  3) категории CoinGecko по `CG2SEC`.
Подсектор — более узкий тег CMC/CoinGecko по `SUBSEC`. Портфели — теги CMC «<фонд>-portfolio» (инвесторы и
маркетмейкеры: DWF Labs, Amber, Alameda, Kenetic и др.). Экосистема — своя сеть у монет первого уровня (`NATIVE`),
иначе сеть контракта CMC (`platform`), иначе тег экосистемы CMC.

Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/sectors.py [fetch] [build]
Сырые ответы — /dev/shm/s275/raw (в памяти), выжимка — /home/user/mc_data/s275/sector_src.json.gz,
таблица — research/s275/sectors.csv."""
import gzip
import json
import os
import pickle
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "s259", "study"))
from common259 import base, crypto_perps  # noqa: E402

RAW = "/dev/shm/s275/raw"
OUT = "/home/user/mc_data/s275"
CSV = os.path.join(HERE, "..", "sectors.csv")
os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}

CG_CATS = ["layer-1", "layer-2", "meme-token", "solana-meme-coins", "dog-themed-coins", "cat-themed-coins",
           "frog-themed-coins", "base-meme-coins", "bnb-chain-meme-coins", "ai-meme-coins", "artificial-intelligence",
           "ai-agents", "decentralized-finance-defi", "decentralized-exchange", "lending-borrowing",
           "decentralized-perpetuals", "derivatives", "liquid-staking", "restaking", "oracle", "gaming",
           "metaverse", "non-fungible-tokens-nft", "real-world-assets-rwa", "depin", "storage", "privacy-coins",
           "zero-knowledge-zk", "interoperability", "modular-blockchain", "exchange-based-tokens", "payment-solutions",
           "fan-token", "pump-fun", "launchpad", "proof-of-work-pow", "telegram-apps", "socialfi"]
# сети (solana-ecosystem, binance-smart-chain, base-ecosystem и др.) берутся из тегов и поля platform CMC —
# у CoinGecko эти категории по тысяче монет и больше, при лимите запросов без ключа их загрузка заняла бы часы


def get(url, tries=6, pause=70):
    for k in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90)
            return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and k < tries - 1:
                print(f"  429 — пауза {pause} с: {url[:90]}", flush=True)
                time.sleep(pause)
                continue
            raise
        except Exception as e:  # сеть
            if k < tries - 1:
                print(f"  сбой {str(e)[:80]} — пауза 20 с", flush=True)
                time.sleep(20)
                continue
            raise


def cached(name, url, **kw):
    f = os.path.join(RAW, name)
    if os.path.exists(f):
        return json.load(open(f))
    j = get(url, **kw)
    json.dump(j, open(f, "w"))
    return j


def fetch():
    W = "https://www.binance.com"
    cached("fx.json", f"{W}/fapi/v1/exchangeInfo"); time.sleep(1)
    cached("fx_price.json", f"{W}/fapi/v1/ticker/price"); time.sleep(1)
    cached("bn_mkt.json", f"{W}/bapi/composite/v1/public/marketing/symbol/list"); time.sleep(1)
    cached("bn_prod.json", f"{W}/bapi/asset/v2/public/asset-service/product/get-products?includeEtf=true"); time.sleep(1)
    for start in (1, 5001):
        cached(f"cmc_{start}.json", "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing?"
               f"start={start}&limit=5000&sortBy=market_cap&sortType=desc&convert=USD&cryptoType=all&tagType=all"
               "&audited=false&aux=tags,platform")
        time.sleep(3)
    for c in CG_CATS:
        for page in (1, 2, 3, 4):
            f = f"cg_{c}_{page}.json"
            if os.path.exists(os.path.join(RAW, f)):
                j = json.load(open(os.path.join(RAW, f)))
            else:
                try:
                    j = cached(f, "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
                               f"&category={c}&order=market_cap_desc&per_page=250&page={page}")
                except urllib.error.HTTPError as e:
                    print(f"  CoinGecko {c}: {e.code}", flush=True)
                    j = []
                time.sleep(13)
            print(f"CoinGecko {c} стр. {page}: {len(j)}", flush=True)
            if len(j) < 250:
                break


# --- словари соответствия -------------------------------------------------------------------------------
BN_SKIP = {"Crypto", "Alpha", "USDC", "Pre-Market", "Cross Pair", "Index", "TradFi", "Pre-IPO", "Chinese"}
BN_MAP = {"Layer-1": "Layer-1", "Layer-2": "Layer-2", "Meme": "Meme", "AI": "AI", "DeFi": "DeFi",
          "Infrastructure": "Infrastructure", "Gaming": "Gaming", "PoW": "PoW", "NFT": "NFT/Metaverse",
          "Metaverse": "NFT/Metaverse", "Payment": "Payment", "Storage": "Storage", "RWA": "RWA", "DEX": "DeFi",
          "CEX": "CEX", "Bitcoin Eco": "Bitcoin-eco"}
# теги CMC → сектор (по порядку приоритета)
CMC2SEC = [("memes", "Meme"), ("animal-memes", "Meme"), ("doggone-doggerel", "Meme"), ("cat-themed", "Meme"),
           ("ai-memes", "Meme"), ("ai-agents", "AI"), ("ai-big-data", "AI"), ("generative-ai", "AI"),
           ("defai", "AI"), ("real-world-assets-protocols", "RWA"), ("tokenized-assets", "RWA"),
           ("gaming", "Gaming"), ("play-to-earn", "Gaming"), ("metaverse", "NFT/Metaverse"),
           ("collectibles-nfts", "NFT/Metaverse"), ("storage", "Storage"), ("filesharing", "Storage"),
           ("layer-2", "Layer-2"), ("rollups", "Layer-2"), ("scaling", "Layer-2"),
           ("decentralized-exchange-dex-token", "DeFi"), ("lending-borowing", "DeFi"), ("derivatives", "DeFi"),
           ("perpetuals", "DeFi"), ("liquid-staking-derivatives", "DeFi"), ("restaking", "DeFi"),
           ("yield-farming", "DeFi"), ("defi", "DeFi"), ("depin", "Infrastructure"), ("oracles", "Infrastructure"),
           ("interoperability", "Infrastructure"), ("cross-chain", "Infrastructure"), ("pow", "PoW"),
           ("mineable", "PoW"), ("payments", "Payment"), ("centralized-exchange", "CEX"), ("fan-token", "Fan"),
           ("layer-1", "Layer-1"), ("platform", "Layer-1"), ("smart-contracts", "Layer-1")]
CG2SEC = [("meme-token", "Meme"), ("artificial-intelligence", "AI"), ("ai-agents", "AI"),
          ("real-world-assets-rwa", "RWA"), ("gaming", "Gaming"), ("metaverse", "NFT/Metaverse"),
          ("non-fungible-tokens-nft", "NFT/Metaverse"), ("storage", "Storage"), ("layer-2", "Layer-2"),
          ("decentralized-exchange", "DeFi"), ("lending-borrowing", "DeFi"), ("decentralized-perpetuals", "DeFi"),
          ("derivatives", "DeFi"), ("liquid-staking", "DeFi"), ("restaking", "DeFi"),
          ("decentralized-finance-defi", "DeFi"), ("depin", "Infrastructure"), ("oracle", "Infrastructure"),
          ("interoperability", "Infrastructure"), ("proof-of-work-pow", "PoW"), ("payment-solutions", "Payment"),
          ("exchange-based-tokens", "CEX"), ("fan-token", "Fan"), ("layer-1", "Layer-1")]
# подсектор — узкий тег (CMC или CoinGecko), по порядку
SUBSEC = [("cmc", "ai-agents", "AI-agents"), ("cg", "ai-agents", "AI-agents"), ("cmc", "ai-memes", "AI-memes"),
          ("cg", "ai-meme-coins", "AI-memes"), ("cmc", "pump-fun-ecosystem", "pump.fun"), ("cg", "pump-fun", "pump.fun"),
          ("cg", "solana-meme-coins", "Solana-memes"), ("cg", "base-meme-coins", "Base-memes"),
          ("cg", "bnb-chain-meme-coins", "BNB-memes"), ("cmc", "four-meme-ecosystem", "BNB-memes"),
          ("cg", "dog-themed-coins", "dog-memes"), ("cmc", "doggone-doggerel", "dog-memes"),
          ("cg", "cat-themed-coins", "cat-memes"), ("cmc", "cat-themed", "cat-memes"),
          ("cg", "frog-themed-coins", "frog-memes"), ("cmc", "liquid-staking-derivatives", "LSD"),
          ("cg", "liquid-staking", "LSD"), ("cmc", "restaking", "restaking"), ("cg", "restaking", "restaking"),
          ("cmc", "perpetuals", "perp-DEX"), ("cg", "decentralized-perpetuals", "perp-DEX"),
          ("cmc", "decentralized-exchange-dex-token", "DEX"), ("cg", "decentralized-exchange", "DEX"),
          ("cmc", "lending-borowing", "lending"), ("cg", "lending-borrowing", "lending"),
          ("cmc", "oracles", "oracle"), ("cg", "oracle", "oracle"), ("cmc", "zero-knowledge-proofs", "ZK"),
          ("cg", "zero-knowledge-zk", "ZK"), ("cmc", "modular-blockchain", "modular"),
          ("cg", "modular-blockchain", "modular"), ("cmc", "depin", "DePIN"), ("cg", "depin", "DePIN"),
          ("cmc", "privacy", "privacy"), ("cg", "privacy-coins", "privacy"), ("cmc", "storage", "storage"),
          ("cmc", "bitcoin-ecosystem", "Bitcoin-eco"), ("cg", "bitcoin-ecosystem", "Bitcoin-eco"),
          ("cmc", "move-vm", "Move-VM"), ("cmc", "telegram-bot", "Telegram"), ("cg", "telegram-apps", "Telegram"),
          ("cmc", "launchpad", "launchpad"), ("cg", "launchpad", "launchpad"), ("cmc", "fan-token", "fan"),
          ("cg", "socialfi", "SocialFi"), ("cmc", "interoperability", "interop"), ("cg", "interoperability", "interop")]
# своя сеть у монет первого уровня и токенов сети (экосистема = сеть)
NATIVE = {"BTC": "Bitcoin", "ETH": "Ethereum", "BNB": "BNB Chain", "SOL": "Solana", "TRX": "Tron", "TON": "TON",
          "SUI": "Sui", "AVAX": "Avalanche", "MATIC": "Polygon", "POL": "Polygon", "ARB": "Arbitrum",
          "OP": "Optimism", "ATOM": "Cosmos", "DOT": "Polkadot", "NEAR": "NEAR", "APT": "Aptos", "ADA": "Cardano",
          "FTM": "Fantom", "S": "Sonic", "SEI": "Sei", "INJ": "Injective", "TIA": "Celestia", "HBAR": "Hedera",
          "XRP": "XRP Ledger", "XLM": "Stellar", "ALGO": "Algorand", "EGLD": "MultiversX", "KAVA": "Kava",
          "CELO": "Celo", "KLAY": "Kaia", "KAIA": "Kaia", "ICP": "ICP", "FIL": "Filecoin", "STX": "Stacks",
          "HYPE": "Hyperliquid", "MNT": "Mantle", "IMX": "Immutable", "STRK": "Starknet", "ZK": "zkSync",
          "BERA": "Berachain", "CORE": "Core", "CFX": "Conflux", "ROSE": "Oasis", "ONE": "Harmony", "XTZ": "Tezos",
          "EOS": "EOS", "A": "Vaulta", "NEO": "NEO", "QTUM": "Qtum", "VET": "VeChain", "ZIL": "Zilliqa",
          "IOTA": "IOTA", "WAVES": "Waves", "MINA": "Mina", "FLOW": "Flow", "RON": "Ronin", "RONIN": "Ronin",
          "METIS": "Metis", "MANTA": "Manta", "BLAST": "Blast", "SCR": "Scroll", "LINEA": "Linea", "DYM": "Dymension",
          "OSMO": "Osmosis", "AXL": "Axelar", "KSM": "Kusama", "ASTR": "Astar", "GLMR": "Moonbeam",
          "MOVR": "Moonriver", "ETC": "Ethereum Classic", "LTC": "Litecoin", "BCH": "Bitcoin Cash", "DOGE": "Dogecoin",
          "KAS": "Kaspa", "TAO": "Bittensor", "XMR": "Monero", "ZEC": "Zcash", "DASH": "Dash", "WLD": "World Chain",
          "BB": "BounceBit", "ENA": "Ethereum", "PLUME": "Plume", "SOPH": "Sophon", "IP": "Story", "MON": "Monad",
          "SONIC": "Sonic", "PI": "Pi", "XDC": "XDC", "THETA": "Theta", "ONT": "Ontology", "ICX": "ICON",
          "LUNA2": "Terra", "LUNC": "Terra Classic", "USTC": "Terra Classic", "1000LUNC": "Terra Classic"}
CMC_PLAT = {"Ethereum": "Ethereum", "BNB Smart Chain (BEP20)": "BNB Chain", "BNB Chain": "BNB Chain",
            "Solana": "Solana", "Base": "Base", "Arbitrum": "Arbitrum", "Toncoin": "TON", "TON": "TON", "Sui": "Sui",
            "Sui Network": "Sui", "Tron20": "Tron", "TRON": "Tron", "Avalanche C-Chain": "Avalanche",
            "Polygon": "Polygon", "Optimism": "Optimism", "Aptos": "Aptos", "Near": "NEAR", "Cosmos": "Cosmos",
            "Fantom": "Fantom", "Sonic": "Sonic", "Hyperliquid": "Hyperliquid", "HyperEVM": "Hyperliquid",
            "Mantle": "Mantle", "zkSync Era": "zkSync", "Starknet": "Starknet", "Linea": "Linea", "Blast": "Blast",
            "Klaytn": "Kaia", "Kaia": "Kaia", "Cardano": "Cardano", "Stellar": "Stellar", "XRP Ledger": "XRP Ledger",
            "Ronin": "Ronin", "Chiliz": "Chiliz", "Chiliz Chain": "Chiliz", "Bitcoin": "Bitcoin",
            "Story": "Story", "Berachain": "Berachain", "Sei V2": "Sei", "Sei": "Sei", "Injective": "Injective",
            "Osmosis": "Cosmos", "Neo": "NEO", "VeChain": "VeChain", "Algorand": "Algorand", "Kava": "Kava",
            "Celo": "Celo", "Ethereum Classic": "Ethereum Classic", "Hedera Hashgraph": "Hedera", "Hedera": "Hedera",
            "Abstract": "Abstract", "Unichain": "Unichain", "World Chain": "World Chain", "Plasma": "Plasma"}
CMC_ECO = [("solana-ecosystem", "Solana"), ("bnb-chain-ecosystem", "BNB Chain"), ("base-ecosystem", "Base"),
           ("toncoin-ecosystem", "TON"), ("sui-ecosystem", "Sui"), ("tron20-ecosystem", "Tron"),
           ("arbitrum-ecosystem", "Arbitrum"), ("avalanche-ecosystem", "Avalanche"), ("hyperevm-ecosystem", "Hyperliquid"),
           ("cosmos-ecosystem", "Cosmos"), ("polkadot", "Polkadot"), ("near-protocol-ecosystem", "NEAR"),
           ("ethereum-ecosystem", "Ethereum")]


# снятые перпы без меток в источниках (часто бывали в топ-100 своих лет): сектор и сеть вручную
MANUAL = {"RNDR": ("Infrastructure", "Ethereum"), "BZRX": ("DeFi", "Ethereum"), "TOMO": ("Layer-1", "TomoChain"),
          "AKRO": ("DeFi", "Ethereum"), "ANC": ("DeFi", "Terra"), "LEND": ("DeFi", "Ethereum"),
          "COCOS": ("Gaming", ""), "RAYSOL": ("DeFi", "Solana"), "BTCST": ("PoW", "BNB Chain")}


def build():
    fx = json.load(open(os.path.join(RAW, "fx.json")))["symbols"]
    FX = {x["symbol"][:-4]: x for x in fx if x["symbol"].endswith("USDT") and x["contractType"] == "PERPETUAL"}
    PX = {x["symbol"][:-4]: float(x["price"]) for x in json.load(open(os.path.join(RAW, "fx_price.json")))
          if x["symbol"].endswith("USDT")}
    MK = {}
    for x in json.load(open(os.path.join(RAW, "bn_mkt.json")))["data"]:
        if x.get("quoteAsset") == "USDT":
            MK[x["baseAsset"]] = x
    PR = {}
    for x in json.load(open(os.path.join(RAW, "bn_prod.json")))["data"]:
        PR.setdefault(x["b"], set()).update(x.get("tags") or [])
    CMC = []
    for start in (1, 5001):
        CMC += json.load(open(os.path.join(RAW, f"cmc_{start}.json")))["data"]["cryptoCurrencyList"]
    CMC_ID = {x["id"]: x for x in CMC}
    CMC_SYM = {}
    for x in CMC:
        CMC_SYM.setdefault(x["symbol"].upper(), []).append(x)

    def mcap(x):
        q = (x.get("quotes") or [{}])[0]
        return float(q.get("marketCap") or 0), float(q.get("price") or 0)
    CG = {}
    for f in sorted(os.listdir(RAW)):
        if f.startswith("cg_"):
            cat = f[3:].rsplit("_", 1)[0]
            for x in json.load(open(os.path.join(RAW, f))) or []:
                d = CG.setdefault(x["id"], dict(sym=x["symbol"].upper(), name=x["name"], mc=x.get("market_cap") or 0,
                                               cats=set()))
                d["cats"].add(cat)
    CG_SYM = {}
    for k, d in CG.items():
        CG_SYM.setdefault(d["sym"], []).append((k, d))

    # перпы всех трёх периодов
    sets = {}
    for name, f in (("p2020", "s117/k_2020.pkl"), ("p2022", "s117/k_oos.pkl"), ("p2024", "s224/k_d.pkl")):
        K = pickle.load(open(f, "rb"))
        sets[name] = set(crypto_perps(K))
        last = {p: float(K[p]["c"][-1]) for p in sets[name]}
        sets[name + "_last"] = last
        del K
    perps = sorted(set().union(sets["p2020"], sets["p2022"], sets["p2024"]))
    rows = []
    for p in perps:
        b = base(p)
        mult = 1.0
        for pre, m in (("1000000", 1e6), ("100000", 1e5), ("10000", 1e4), ("1000", 1e3), ("1M", 1e6)):
            if p.startswith(pre) and p != b:
                mult = m
                break
        fxr = FX.get(p)
        bn_sub = [t for t in (fxr or {}).get("underlyingSubType", []) if t not in BN_SKIP]
        mk = MK.get(b) or MK.get(p)
        bn_tags = sorted(set((mk or {}).get("tags") or []) | PR.get(b, set()) | PR.get(p, set()))
        # CMC
        how, cm = "", None
        if mk and mk.get("cmcUniqueId") in CMC_ID:
            cm, how = CMC_ID[mk["cmcUniqueId"]], "cmcUniqueId Binance"
        else:
            cands = sorted(CMC_SYM.get(b.upper(), []), key=lambda x: -mcap(x)[0])
            px = PX.get(p) or sets["p2024_last"].get(p)
            if px:
                ok = [x for x in cands if mcap(x)[1] > 0 and 0.8 <= (px / mult) / mcap(x)[1] <= 1.25]
                if ok:
                    cm, how = ok[0], "тикер + цена"
            if cm is None and cands:
                cm, how = cands[0], "тикер (наибольшая капитализация)"
        tags = set(cm.get("tags") or []) if cm else set()
        plat = ((cm or {}).get("platform") or {}).get("name") if cm else None
        # CoinGecko
        cg = None
        for k, d in CG_SYM.get(b.upper(), []):
            if cm and (d["name"].lower() == cm["name"].lower() or
                       (mcap(cm)[0] > 0 and d["mc"] and 0.6 <= d["mc"] / mcap(cm)[0] <= 1.67)):
                cg = (k, d)
                break
        if cg is None and len(CG_SYM.get(b.upper(), [])) == 1 and not cm:
            cg = CG_SYM[b.upper()][0]
        cats = cg[1]["cats"] if cg else set()
        # сектор
        sec, src = None, ""
        if bn_sub:
            sec, src = BN_MAP.get(bn_sub[0], bn_sub[0]), "Binance underlyingSubType"
        if sec is None:
            for t, s in CMC2SEC:
                if t in tags:
                    sec, src = s, f"CMC {t}"
                    break
        if sec is None:
            for t, s in CG2SEC:
                if t in cats:
                    sec, src = s, f"CoinGecko {t}"
                    break
        if sec is None and p in MANUAL:
            sec, src = MANUAL[p][0], "вручную (снятый перп)"
        if sec is None and {"Layer1_Layer2"} & set(bn_tags):
            sec, src = "Layer-1", "Binance тег Layer1_Layer2"
        if sec is None and "defi" in bn_tags:
            sec, src = "DeFi", "Binance тег defi"
        sub = ""
        for srcn, t, s in SUBSEC:
            if (srcn == "cmc" and t in tags) or (srcn == "cg" and t in cats):
                sub = s
                break
        if sec == "Meme" and not sub:
            sub = "memes"
        # экосистема
        eco, eco_src = None, ""
        if b in NATIVE:
            eco, eco_src = NATIVE[b], "своя сеть"
        elif plat:
            eco, eco_src = CMC_PLAT.get(plat, plat), "сеть контракта CMC"
        else:
            for t, e in CMC_ECO:
                if t in tags:
                    eco, eco_src = e, f"тег CMC {t}"
                    break
        if eco is None and p in MANUAL and MANUAL[p][1]:
            eco, eco_src = MANUAL[p][1], "вручную (снятый перп)"
        if eco is None and "Solana" in bn_tags:
            eco, eco_src = "Solana", "тег Binance Solana"
        if eco is None and "BSC" in bn_tags:
            eco, eco_src = "BNB Chain", "тег Binance BSC"
        eco_tags = [e for t, e in CMC_ECO if t in tags]
        rows.append(dict(perp=p, coin=b, in_2020=int(p in sets["p2020"]), in_2022=int(p in sets["p2022"]),
                         in_2024=int(p in sets["p2024"]), listed=int(fxr is not None and fxr.get("status") == "TRADING"),
                         sector=sec or "", subsector=sub, eco=eco or "", sector_src=src, eco_src=eco_src,
                         bn_sub="|".join((fxr or {}).get("underlyingSubType", [])),
                         bn_tags="|".join(t for t in bn_tags if t not in ("Monitoring", "Seed", "newListing")),
                         cmc_id=(cm or {}).get("id", ""), cmc_slug=(cm or {}).get("slug", ""), cmc_match=how,
                         cmc_mcap=round(mcap(cm)[0]) if cm else "", platform=plat or "",
                         eco_tags="|".join(eco_tags),
                         cmc_sector_tags="|".join(t for t, _ in CMC2SEC if t in tags),
                         cg_id=cg[0] if cg else "", cg_cats="|".join(sorted(cats)),
                         portfolios="|".join(sorted(t[:-10] for t in tags if t.endswith("-portfolio")))))
    import csv
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with gzip.open(os.path.join(OUT, "sector_src.json.gz"), "wt") as f:
        json.dump(dict(cmc={x["id"]: dict(sym=x["symbol"], slug=x["slug"], tags=x.get("tags"),
                                          platform=(x.get("platform") or {}).get("name")) for x in CMC
                            if x["symbol"].upper() in {r["coin"].upper() for r in rows}},
                       bn_sub={k: v.get("underlyingSubType") for k, v in FX.items()},
                       cg={k: dict(sym=d["sym"], name=d["name"], cats=sorted(d["cats"])) for k, d in CG.items()}), f)
    print(f"таблица: {len(rows)} перпов → {CSV}")


if __name__ == "__main__":
    a = sys.argv[1:] or ["fetch", "build"]
    if "fetch" in a:
        fetch()
    if "build" in a:
        build()
