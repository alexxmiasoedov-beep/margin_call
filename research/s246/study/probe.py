"""s246: повторная проверка источников без ключа (код ответа и короткая пометка). Запуск: python3 -I probe.py
Итог пишется в /home/user/mc_data/s246/probe.log. Личных данных и ключей не используется."""
import json, urllib.request, urllib.error, time, datetime
UA = "research-script/1.0"
GQL_LOCKUP = "https://indexer.hyperindex.xyz/53b7e25/v1/graphql"
GQL_AIRDROP = "https://indexer.hyperindex.xyz/508d217/v1/graphql"
SAFE = "0x849D52316331967b6fF1198e5E32A0eB168D039d"   # публичная казна GnosisDAO
LOGS = {"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [{"fromBlock": "0x1C9C380", "toBlock": "0x1C9C3E4",
        "address": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"]}]}
CHECKS = [
    ("Sablier Lockup (Envio)", GQL_LOCKUP, {"query": "{ LockupAction(limit:1, where:{category:{_eq:\"Withdraw\"}}){ id timestamp } }"}),
    ("Sablier Airdrops (Envio)", GQL_AIRDROP, {"query": "{ Campaign(limit:1){ id timestamp } }"}),
    ("Binance CMS 161 Delisting", "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=1&catalogId=161", None),
    ("Binance CMS 157 Maintenance", "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=1&catalogId=157", None),
    ("Binance fapi exchangeInfo (www)", "https://www.binance.com/fapi/v1/exchangeInfo", None),
    ("data.binance.vision klines снятого перпа", "https://data.binance.vision/data/futures/um/daily/klines/ALPACAUSDT/15m/ALPACAUSDT-15m-2025-04-30.zip", None),
    ("data.binance.vision liquidationSnapshot", "https://data.binance.vision/data/futures/um/daily/liquidationSnapshot/BTCUSDT/BTCUSDT-liquidationSnapshot-2023-03-01.zip", None),
    ("Safe tx-service (api.safe.global)", f"https://api.safe.global/tx-service/eth/api/v1/safes/{SAFE}/multisig-transactions/?limit=1", None),
    ("CoW orderbook API", f"https://api.cow.fi/mainnet/api/v1/account/{SAFE}/orders?limit=1", None),
    ("Coinbase Derivatives products", "https://api.coinbase.com/api/v3/brokerage/market/products?product_type=FUTURE&limit=5", None),
    ("OKX announcements", "https://www.okx.com/api/v5/support/announcements?page=1", None),
    ("Bybit announcements", "https://api.bybit.com/v5/announcements/index?locale=en-US&limit=1", None),
    ("DefiLlama holders revenue", "https://api.llama.fi/summary/fees/hyperliquid?dataType=dailyHoldersRevenue", None),
    ("DefiLlama raises", "https://api.llama.fi/raises", None),
    ("Wormholescan governor queue", "https://api.wormholescan.io/api/v1/governor/enqueued_vaas", None),
    ("BNB Chain archive: publicnode", "https://bsc-rpc.publicnode.com", LOGS),
    ("BNB Chain archive: Envio HyperRPC", "https://bsc.rpc.hypersync.xyz", LOGS),
    ("Wayback available", "http://archive.org/wayback/available?url=defillama.com/unlocks", None),
]

def check(name, url, body):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            txt = r.read(400).decode('utf-8', 'replace')
            code = r.status
    except urllib.error.HTTPError as e:
        code, txt = e.code, e.read(200).decode('utf-8', 'replace')
    except Exception as e:
        code, txt = 0, str(e)[:120]
    if 'error' in txt[:200].lower() and code == 200:
        code = f"200, ошибка в ответе"
    return code, txt.replace('\n', ' ')[:110]

if __name__ == '__main__':
    out = [f"# probe {datetime.datetime.now(datetime.UTC):%Y-%m-%d %H:%M} UTC"]
    for name, url, body in CHECKS:
        code, txt = check(name, url, body)
        out.append(f"{name} | {code} | {txt}")
        time.sleep(0.5)
    open('/home/user/mc_data/s246/probe.log', 'w').write('\n'.join(out) + '\n')
    print('\n'.join(out))
