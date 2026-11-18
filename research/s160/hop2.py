import json, sys, time, urllib.request, random, collections, re
UA={"User-Agent":"research-script/1.0"}
S=json.load(open('sets.json')); cex=S['cex']; toks=S['toks']
inv={v['sym']:k for k,v in toks.items()}
CUST={'Coinbase Prime','Anchorage Digital','FalconX','Bitcoin Suisse','Copper','BitGo','Fireblocks','Cumberland','Galaxy Digital','Wintermute','Amber Group','Matrixport','Ceffu','Hex Trust','Komainu','Cobo','Paxos'}
STAB={'USDC','USDT','DAI','FDUSD','TUSD','BUSD','USDE','USD1','PYUSD','USDS'}
def get(url, data=None, hdr=None):
    for k in range(4):
        try:
            req=urllib.request.Request(url,data=data,headers=hdr or UA)
            with urllib.request.urlopen(req,timeout=40) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(2+3*k)
    return None
def is_contract(a):
    d=get("https://gateway.tenderly.co/public/mainnet", json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_getCode","params":[a,"latest"]}).encode(), {"User-Agent":"research-script/1.0","Content-Type":"application/json"})
    return bool(d and d.get('result') not in (None,'0x'))
def meta(addrs):
    out={}
    for i in range(0,len(addrs),40):
        d=get("https://metadata.services.blockscout.com/api/v1/metadata?chainId=1&addresses="+",".join(addrs[i:i+40]))
        for a,v in ((d or {}).get('addresses') or {}).items():
            out[a.lower()]=[t['name'] for t in v.get('tags',[])]
    return out
MMRE=re.compile(r'wintermute|dwf|gsr|amber|flowdesk|galaxy|cumberland|jump|falconx|b2c2|auros|selini|presto|kronos|gotbit|market maker|alameda|laser|qcp|flow traders|nonce|symbolic|spartan|maven|polychain|paradigm|a16z|andreessen|multicoin|pantera|dragonfly|hashed|delphi|mechanism|electric|ventures|capital|fund|blockchain capital|three arrows|celsius|otc', re.I)
TEAMRE=re.compile(r'team|vesting|treasury|foundation|deployer|dao|multisig|ecosystem|reserve|unlock|claim|airdrop|distribution|token sale|grant|community|staking|rewards|safe', re.I)
EXRE=re.compile(r'exchange|binance|okx|okex|coinbase|bybit|kucoin|gate|htx|huobi|mexc|kraken|upbit|bithumb|bitget|crypto\.com|bitfinex|hot wallet|deposit|ftx|bittrex|poloniex|paribu|btcturk|bitvavo|gemini|bitstamp', re.I)
def run(lbl, n=int(__import__("os").environ.get("HOPN","60")), seed=7):
    big=json.load(open(f'sweeps/{lbl}_big.json'))
    ev=[b for b in big if b[0]>=0.005 and b[7] not in CUST and b[1] not in STAB and not b[5].startswith('0x0000000000')]
    seen=set(); uniq=[]
    for b in ev:
        k=(b[1],b[4][:5])
        if k in seen: continue
        seen.add(k); uniq.append(b)
    random.seed(seed); smp=random.sample(uniq, min(n,len(uniq)))
    recs=[]
    for b in smp:
        frac,sym,perp,amt,when,dep,to,exch,tx,src=b
        tok=inv.get(sym)
        d=get(f"https://eth.blockscout.com/api?module=account&action=tokentx&address={dep}&contractaddress={tok}&page=1&offset=100&sort=desc")
        rs=(d or {}).get('result') or []
        inc=[r for r in rs if r['to'].lower()==dep.lower()]
        tot=collections.Counter()
        for r in inc: tot[r['from'].lower()]+=int(r['value'])
        top=tot.most_common(1)[0][0] if tot else None
        # deposit address behaviour: does dep forward everything to exchange (sweep pattern)?
        outs=[r for r in rs if r['from'].lower()==dep.lower()]
        out_to_cex=sum(1 for r in outs if r['to'].lower() in cex)
        recs.append(dict(sym=sym,frac=frac,when=when,exch=exch,dep=dep,top=top,n_in=len(inc),n_out=len(outs),out_to_cex=out_to_cex))
        time.sleep(0.3)
    tops=[r['top'] for r in recs if r['top']]
    M=meta(list(set(tops)))
    for r in recs:
        t=r['top']
        if not t: r['cls']='direct/no inflow'; r['lab']=''; continue
        lab=' '.join(M.get(t,[]))
        r['lab']=lab[:60]
        if t in cex or EXRE.search(lab): r['cls']='from exchange'
        elif MMRE.search(lab): r['cls']='MM/VC/OTC label'
        elif TEAMRE.search(lab): r['cls']='team/treasury/vesting label'
        elif lab: r['cls']='other label'
        else:
            r['cls']='unlabeled contract' if is_contract(t) else 'unlabeled EOA'
    c=collections.Counter(r['cls'] for r in recs)
    print('==',lbl,'sample',len(recs),dict(c), flush=True)
    for r in recs: print('   ', r['cls'], r['sym'], f"{r['frac']*100:.2f}%", r['when'], r['exch'], 'in',r['n_in'],'out',r['n_out'],'->cex',r['out_to_cex'], '|', r['lab'])
    json.dump(recs, open(f'sweeps/{lbl}_hop.json','w'))
for lbl in sys.argv[1:]: run(lbl)
