import json, sys, time, urllib.request, random, collections, re
UA={"User-Agent":"research-script/1.0"}
S=json.load(open('sets.json')); cex=S['cex']; toks=S['toks']
inv={v['sym']:k for k,v in toks.items()}
def get(url):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=60) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(3+3*k)
    return None
def tags(a):
    m=a.get('metadata') or {}
    return [x.get('name') for x in (m.get('tags') or [])]
MMRE=re.compile(r'wintermute|dwf|gsr|amber|flowdesk|galaxy|cumberland|jump|falconx|b2c2|auros|selini|presto|kronos|gotbit|market maker|alameda|laser|qcp|flow traders|nonce|symbolic|spartan|maven|polychain|paradigm|a16z|multicoin|pantera|dragonfly|hashed|delphi|mechanism|electric|ventures|capital|labs|fund|digital', re.I)
TEAMRE=re.compile(r'team|vesting|treasury|foundation|deployer|dao|multisig|ecosystem|reserve|unlock|claim|airdrop|distribution|token sale|grant|community|staking|rewards', re.I)
def classify(big, n=40, seed=1):
    random.seed(seed)
    ev=[b for b in big if b[0]>=0.005 and b[7] not in ('Coinbase Prime','Anchorage Digital','FalconX','Bitcoin Suisse','Copper','BitGo','Fireblocks')]
    # one per token-day
    seen=set(); uniq=[]
    for b in ev:
        k=(b[1],b[4][:5])
        if k in seen: continue
        seen.add(k); uniq.append(b)
    smp=random.sample(uniq, min(n,len(uniq)))
    out=[]
    for b in smp:
        frac,sym,perp,amt,when,fr,to,exch,tx,src=b
        tok=inv.get(sym)
        d=get(f"https://eth.blockscout.com/api/v2/addresses/{fr}/token-transfers?type=ERC-20&filter=to&token={tok}")
        time.sleep(0.4)
        senders=collections.Counter(); info={}
        for it in (d or {}).get('items',[])[:50]:
            f=it['from']; v=int(it['total']['value'])
            senders[f['hash'].lower()]+=v
            info[f['hash'].lower()]=(f.get('name'), tags(f), f.get('is_contract'))
        if not senders:
            cls='direct (no prior inflow seen)'; top=None
        else:
            top=senders.most_common(1)[0][0]
            nm,tg,isc=info[top]
            lab=' '.join([nm or '']+[t or '' for t in tg])
            if top in cex or re.search(r'exchange|binance|okx|coinbase|bybit|kucoin|gate|htx|huobi|mexc|kraken|upbit|bithumb|bitget|crypto\.com|bitfinex', lab, re.I): cls='from exchange'
            elif MMRE.search(lab): cls='MM/fund label'
            elif TEAMRE.search(lab): cls='team/treasury/vesting label'
            elif isc: cls='unlabeled contract'
            elif lab.strip(): cls='other label: '+lab[:40]
            else: cls='unlabeled EOA'
        out.append((cls, sym, round(frac*100,2), when, exch, (info.get(top,('', [],None))[0] or '') + ' ' + ','.join([t for t in info.get(top,('',[],None))[1] if t][:3]) if top else ''))
    return out
if __name__=="__main__":
    for p in sys.argv[1:]:
        big=json.load(open(p))
        out=classify(big)
        print('==',p, collections.Counter(o[0] if not o[0].startswith('other label') else 'other label' for o in out))
        for o in out: print('   ',o)
