import json, re, sys, collections, pickle
perps=set(pickle.load(open('/home/user/mc_data/s2/fund2y.pkl','rb')).keys())
def perp_of(sym):
    for p in (sym, '1000'+sym, '1000000'+sym):
        if p in perps: return p
    return None
EXCH=r'(Binance|OKX|Bybit|Coinbase|Bitget|Gate|KuCoin|HTX|Huobi|MEXC|Kraken|Upbit|Bithumb|Crypto\.com|Bitfinex|Bitstamp|Gemini|BingX|Bitvavo|Robinhood|WhiteBIT|Binance US|Kucoin)'
MM=r'(Wintermute|DWF|GSR|Amber|Flowdesk|Galaxy|Cumberland|Jump|FalconX|B2C2|Auros|Selini|Presto|Abraxas|Arrington|Cypher|Kronos|Gotbit|Mantle|Laser Digital|Flow Traders|QCP|Nonce|Bluesky|Symbolic|Spartan|Maven 11|Polychain|Paradigm|a16z|Multicoin|Pantera|Dragonfly|Hashed|Delphi|Mechanism|Electric|Coinbase Ventures|Binance Labs|YZi|Framework|Placeholder|Blockchain Capital|Fenbushi|Hack VC|Animoca|Sequoia|Jane Street|Arca|Andreessen|Alameda|Three Arrows|3AC|Celsius|FTX)'
STABLE={'USDT','USDC','DAI','USDE','FDUSD','PYUSD','USD1','USDS','TUSD','BUSD','RLUSD','USDG','EURC'}
BIG={'BTC','ETH','WBTC','WETH','STETH','WSTETH','CBBTC','SOL'}
def analyze(path):
    d=json.load(open(path))
    rows=[]
    for pid,t,s in d:
        dep=re.search(r'(deposit\w*|sent|transferr?ed|moved)\b[^.\n]*?\b(to|into)\s+#?'+EXCH, s, re.I)
        if not dep: continue
        syms=[x.upper() for x in re.findall(r'\$([A-Za-z0-9]{2,12})\b', s)]
        alts=[x for x in syms if x not in STABLE and x not in BIG and not x.isdigit()]
        if not alts: continue
        cat='whale/other'
        if re.search(MM, s): cat='MM/VC/fund'
        if re.search(r'\b(team|project|foundation|treasury|vesting|unlock|deployer|dev|developer|insider|investor)\b', s, re.I): cat = cat if cat!='whale/other' else 'team/insider/investor'
        rows.append((t[:10], alts[0], perp_of(alts[0]) is not None, cat, s[:160].replace('\n',' ')))
    return d, rows
for p in sys.argv[1:]:
    d,rows=analyze(p)
    print(f"== {p}: posts {len(d)}, alt deposits to CEX {len(rows)}, with Binance perp {sum(r[2] for r in rows)}")
    print(collections.Counter(r[3] for r in rows if r[2]))
    for r in rows[:40]: print('  ',r[0], r[1], 'perp' if r[2] else '-', r[3], '|', r[4][:150])
