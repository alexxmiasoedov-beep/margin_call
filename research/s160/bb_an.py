import json, re, sys, collections, pickle
perps=set(pickle.load(open('/home/user/mc_data/s2/fund2y.pkl','rb')).keys())
def perp_of(sym):
    for p in (sym, '1000'+sym, '1000000'+sym):
        if p in perps: return p
    return None
EX=r'(币安|Binance|OKX|欧易|Bybit|Coinbase|Bitget|Gate|KuCoin|HTX|火币|MEXC|Kraken|Upbit|Bithumb|交易所|CEX|Hyperliquid)'
DEP=r'(存入|转入|充值|充入|转至|转移至|deposit)'
MON=r'(Lookonchain|余烬|Ember|Spot On Chain|Onchain Lens|Ai\s*姨|Arkham|链上|监测|EmberCN|PeckShield|Whale Alert|Scopescan|MLM|Nansen|Debank|DeBank|Cointelegraph)'
MM=r'(做市商|Wintermute|DWF|GSR|Amber|Flowdesk|Galaxy|Cumberland|Jump|FalconX|B2C2|Auros|Selini|Presto|Abraxas|Gotbit|Laser)'
TEAM=r'(团队|项目方|基金会|国库|开发者|多签|部署|生态|金库|Treasury|Foundation|Team)'
VC=r'(机构|投资机构|风投|VC|投资方|早期投资者|私募|Polychain|Paradigm|a16z|Multicoin|Pantera|Maven|Spartan|Hashed|Delphi|Mechanism|Arrington|Fenbushi|Animoca|Coinbase Ventures|Binance Labs|YZi)'
UNL=r'(解锁)'
STABLE={'USDT','USDC','DAI','USDE','FDUSD','PYUSD','USD1','USDS','TUSD','BUSD','RLUSD','USDG','EURC','ETF','CEX','DEX','USD','AI','RWA','TVL','DAO','NFT','SEC','CEO','API','APP','UTC','OTC','PNL'}
BIG={'BTC','ETH','WBTC','WETH','STETH','WSTETH','CBBTC','SOL','BNB','XRP','TRX'}
def analyze(path):
    d=json.load(open(path))
    rows=[]
    for pid,t,s in d:
        if not re.search(DEP, s, re.I) or not re.search(EX, s): continue
        syms=re.findall(r'枚\s*\$?([A-Za-z][A-Za-z0-9]{1,11})', s)+re.findall(r'\$([A-Za-z][A-Za-z0-9]{1,11})', s)
        syms=[x.upper() for x in syms]
        alts=[x for x in syms if x not in STABLE and x not in BIG]
        if not alts: continue
        cat=[]
        if re.search(MM, s): cat.append('MM')
        if re.search(VC, s): cat.append('VC')
        if re.search(TEAM, s): cat.append('team')
        if re.search(UNL, s): cat.append('unlock')
        if re.search(r'(巨鲸|鲸鱼|whale)', s, re.I): cat.append('whale')
        rows.append((t[:10], alts[0], perp_of(alts[0]) is not None, '+'.join(cat) or 'other', bool(re.search(MON,s)), s[:200].replace('\n',' ')))
    return d, rows
for p in sys.argv[1:]:
    d,rows=analyze(p)
    pr=[r for r in rows if r[2]]
    print(f"== {p}: posts {len(d)}, alt deposit-to-CEX posts {len(rows)}, with Binance perp {len(pr)}, unique token-days {len(set((r[0],r[1]) for r in pr))}")
    c=collections.Counter()
    for r in pr:
        k=r[3]
        c['MM' if 'MM' in k else 'VC/инвест' if 'VC' in k else 'team/фонд' if 'team' in k else 'unlock' if 'unlock' in k else 'whale' if 'whale' in k else 'other']+=1
    print(' categories (perp):', c)
    print(' top tokens:', collections.Counter(r[1] for r in pr).most_common(15))
    for r in pr[:25]: print('  ', r[0], r[1], r[3], '|', r[5][:170])
