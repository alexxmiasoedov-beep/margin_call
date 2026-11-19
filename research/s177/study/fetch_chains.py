"""s177 — выгрузка рядов по сетям (бесплатно, без ключей). Только загрузка, доходы не считаются.

  stablecoins.llama.fi/stablecoincharts/<сеть>     — стейблкоины в сети по дням (все сети из /stablecoinchains);
  api.llama.fi/v2/historicalChainTvl/<сеть>        — TVL сети в $ по дням;
  api.llama.fi/overview/dexs/<сеть>                — оборот DEX сети по дням;
  api.coingecko.com/api/v3/coins/markets?category= — состав «экосистем» CoinGecko (для привязки монет к сетям).
bridges.llama.fi и yields chartLendBorrow отвечают 402 (платно) — не берутся.
Кэш — <папка данных>/s177/chains/. Запуск: python3 -I fetch_chains.py [папка данных]
"""
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
OUT = os.path.join(D, "s177", "chains")
for sub in ("sc", "tvl", "dex", "cg"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
UA = {"User-Agent": "research-script/1.0", "Accept-Encoding": "gzip"}

CG = {  # категория CoinGecko → сеть DefiLlama; число страниц по 250
    "solana-ecosystem": ("Solana", 3), "solana-meme-coins": ("Solana", 1), "base-ecosystem": ("Base", 2),
    "base-meme-coins": ("Base", 1), "sui-ecosystem": ("Sui", 1), "sui-meme": ("Sui", 1),
    "arbitrum-ecosystem": ("Arbitrum", 1), "avalanche-ecosystem": ("Avalanche", 1),
    "binance-smart-chain": ("BSC", 3), "polygon-ecosystem": ("Polygon", 1), "aptos-ecosystem": ("Aptos", 1),
    "near-protocol-ecosystem": ("Near", 1), "ton-ecosystem": ("TON", 1), "ton-meme-coins": ("TON", 1),
    "tron-ecosystem": ("Tron", 1), "tron-meme": ("Tron", 1), "hyperliquid-ecosystem": ("Hyperliquid L1", 1),
    "hyperevm-ecosystem": ("Hyperliquid L1", 1), "sei-v2-ecosystem": ("Sei", 1),
    "berachain-ecosystem": ("Berachain", 1), "sonic-ecosystem": ("Sonic", 1),
    "optimism-ecosystem": ("OP Mainnet", 1), "cardano-ecosystem": ("Cardano", 1),
    "injective-ecosystem": ("Injective", 1), "starknet-ecosystem": ("Starknet", 1),
    "zksync-ecosystem": ("zkSync Era", 1), "linea-ecosystem": ("Linea", 1), "mantle-ecosystem": ("Mantle", 1),
    "blast-ecosystem": ("Blast", 1), "fantom-ecosystem": ("Fantom", 1), "cronos-ecosystem": ("Cronos", 1),
    "xrp-ledger-ecosystem": ("XRPL", 1), "stellar-ecosystem": ("Stellar", 1), "algorand-ecosystem": ("Algorand", 1),
    "hedera-ecosystem": ("Hedera", 1), "klaytn-ecosystem": ("Kaia", 1), "flare-network-ecosystem": ("Flare", 1),
    "monad-ecosystem": ("Monad", 1), "plasma-ecosystem": ("Plasma", 1), "world-chain-ecosystem": ("World Chain", 1),
    "unichain-ecosystem": ("Unichain", 1), "story-ecosystem": ("Story", 1), "abstract-ecosystem": ("Abstract", 1),
    "ronin-ecosystem": ("Ronin", 1), "stacks-ecosystem": ("Stacks", 1), "multiversx-ecosystem": ("MultiversX", 1),
    "kava-ecosystem": ("Kava", 1), "ethereum-ecosystem": ("Ethereum", 2),
}


def get(url, tries=4, pause=10):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return r.status, raw
        except urllib.error.HTTPError as e:
            if e.code in (400, 402, 404) or (e.code == 500 and a >= 1):
                return e.code, b""  # 500 у overview/dexs = у сети нет данных DEX; один повтор и дальше
            print("  HTTP", e.code, url[:90], flush=True)
            if e.code == 500:
                time.sleep(3)
                continue
            if e.code == 429:
                time.sleep(60)
        except Exception as e:  # сеть: пауза и повтор
            print("  ошибка", type(e).__name__, str(e)[:80], flush=True)
        time.sleep(pause * (a + 1))
    return None, b""


def save(sub, name, url, pause):
    fn = os.path.join(OUT, sub, name.replace("/", "_") + ".json.gz")
    if os.path.exists(fn):
        return True
    code, raw = get(url)
    time.sleep(pause)
    if code == 200 and raw:
        with gzip.open(fn, "wb") as f:
            f.write(raw)
        return True
    print(f"  {sub} {name}: нет ({code})", flush=True)
    return False


def main():
    code, raw = get("https://stablecoins.llama.fi/stablecoinchains")
    chains_sc = [x["name"] for x in json.loads(raw)]
    code, raw = get("https://api.llama.fi/v2/chains")
    chains_tvl = json.loads(raw)
    with open(os.path.join(OUT, "v2_chains.json"), "wb") as f:
        f.write(raw)
    n = 0
    for c in chains_sc:
        n += save("sc", c, "https://stablecoins.llama.fi/stablecoincharts/" + urllib.parse.quote(c), 0.4)
    print("стейблкоины по сетям:", n, "из", len(chains_sc), flush=True)
    # TVL и DEX — сети с TVL ≥ 5 млн $ сейчас или со стейблкоинами в списке
    big = sorted({x["name"] for x in chains_tvl if (x.get("tvl") or 0) >= 5e6} | set(chains_sc))
    n1 = n2 = 0
    for c in big:
        q = urllib.parse.quote(c)
        n1 += save("tvl", c, "https://api.llama.fi/v2/historicalChainTvl/" + q, 0.4)
        n2 += save("dex", c, f"https://api.llama.fi/overview/dexs/{q}?excludeTotalDataChart=false"
                             "&excludeTotalDataChartBreakdown=true", 0.4)
    print("TVL сетей:", n1, "DEX сетей:", n2, "из", len(big), flush=True)
    for cat, (ch, pages) in CG.items():
        for p in range(1, pages + 1):
            save("cg", f"{cat}_{p}", "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
                                     f"&category={cat}&order=market_cap_desc&per_page=250&page={p}", 7)
    print("категории CoinGecko: готово", flush=True)


if __name__ == "__main__":
    main()
