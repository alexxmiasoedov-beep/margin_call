import json, pickle, re, collections
f=pickle.load(open('/home/user/mc_data/s2/fund2y.pkl','rb'))
perps=sorted(f.keys())
mk=json.load(open('cg_markets.json'))
plat={x['id']:x.get('platforms',{}) for x in json.load(open('cg_plat.json'))}
bysym={}
for x in mk:  # ordered by mcap desc -> first wins
    s=x['symbol'].upper()
    bysym.setdefault(s,x)
def base(p):
    b=re.sub(r'^(1000000|100000|10000|1000|1M)','',p)
    return b
rows=[]; miss=[]
for p in perps:
    b=base(p)
    x=bysym.get(b) or bysym.get(p)
    if not x: miss.append(p); continue
    pl=plat.get(x['id'],{}) or {}
    pl={k:v for k,v in pl.items() if v}
    rows.append(dict(perp=p,id=x['id'],sym=b,mcap=x.get('market_cap'),circ=x.get('circulating_supply'),price=x.get('current_price'),
                     eth=pl.get('ethereum'),bsc=pl.get('binance-smart-chain'),sol=pl.get('solana'),base=pl.get('base'),arb=pl.get('arbitrum-one'),tron=pl.get('tron'),nplat=len(pl)))
print('perps',len(perps),'mapped',len(rows),'miss',len(miss))
c=collections.Counter()
for r in rows:
    if r['nplat']==0: c['native (no contract)']+=1
    elif r['eth']: c['has ethereum']+=1
    elif r['bsc']: c['bsc (no eth)']+=1
    elif r['sol']: c['solana (no eth/bsc)']+=1
    elif r['base']: c['base only']+=1
    else: c['other chain']+=1
print(c)
json.dump(rows,open('perp_map.json','w'))
print(miss[:60])
