import json, collections, sys
CUST={'Coinbase Prime','Anchorage Digital','FalconX','Bitcoin Suisse','Copper','BitGo','Fireblocks','Cumberland','Galaxy Digital','Wintermute','Amber Group','Matrixport','Ceffu','Hex Trust','Komainu','Cobo','Paxos','Zodia','Bakkt','Fidelity'}
STAB={'USDC','USDT','DAI','FDUSD','TUSD','BUSD','USDE','USD1','PYUSD','USDS'}
def months(lbl): return 1.0
res={}
for lbl in sys.argv[1:]:
    big=json.load(open(f'sweeps/{lbl}_big.json'))
    out={}
    for thr in (0.0025,0.005,0.01):
        ev=[b for b in big if b[0]>=thr and b[1] not in STAB and not b[5].startswith('0x000000000000000000000000000000000000') and b[5]!='0x0000000000000000000000000000000000000000']
        ob=[b for b in ev if b[7] not in CUST]
        cu=[b for b in ev if b[7] in CUST]
        # cooldown 48h per token: sort by time string 'MM-DD HH:MM'
        def cd(lst):
            last={}; n=0; toks=set()
            for b in sorted(lst, key=lambda x:x[4]):
                m,d=b[4][:2],b[4][3:5]; h=int(b[4][6:8])
                tt=int(d)*24+h
                if b[1] in last and tt-last[b[1]]<48: continue
                last[b[1]]=tt; n+=1; toks.add(b[1])
            return n, len(toks)
        out[thr]=dict(orderbook=cd(ob), custody=cd(cu))
    exch=collections.Counter(b[7] for b in big if b[0]>=0.005)
    print(lbl, {f"{k*100:.2f}%":v for k,v in out.items()}, 'dest top:', exch.most_common(8))
