import json, time, urllib.request, sys, gzip, os
UA={"User-Agent":"research-script/1.0","Content-Type":"application/json"}
T0="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
S=json.load(open('sets.json'))
cex=list(S['cex'].keys()); toks=list(S['toks'].keys())
named=[a for a in cex if S['cex'][a][0]!='blockscout-exchange']; extra=[a for a in cex if S['cex'][a][0]=='blockscout-exchange']
allc=named+extra
CH=1000
chunks=[allc[i:i+CH] for i in range(0,len(allc),CH)]
URLS=["https://gateway.tenderly.co/public/mainnet","https://rpc.mevblocker.io"]
def pad(a): return "0x"+"0"*24+a[2:]
stats={'calls':0,'errs':0}
def call(url, params, timeout=90):
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_getLogs","params":[params]}).encode()
    stats['calls']+=1
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=body,headers=UA),timeout=timeout) as r:
            d=json.load(r)
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} {e.read()[:200]}"
    except Exception as e:
        return None, f"EXC {type(e).__name__} {str(e)[:150]}"
    return d.get("result"), d.get("error")
def fetch(a,b,ch,depth=0):
    q={"fromBlock":hex(a),"toBlock":hex(b),"address":toks,"topics":[T0,None,[pad(x) for x in ch]]}
    for attempt in range(6):
        url=URLS[attempt%2]
        r,e=call(url,q)
        if isinstance(r,list): return r
        es=str(e)
        stats['errs']+=1
        if 'more than' in es or 'results' in es and 'limit' in es.lower():
            m=(a+b)//2
            return fetch(a,m,ch,depth+1)+fetch(m+1,b,ch,depth+1)
        time.sleep(2+2*attempt)
    raise RuntimeError(f"fail {a}-{b}: {e}")
def run(a,b,out,step=10000):
    rows=[]
    t=time.time()
    for s in range(a,b,step):
        e_=min(b,s+step-1)
        for ch in chunks:
            for x in fetch(s,e_,ch):
                rows.append((int(x['blockNumber'],16), x['address'], '0x'+x['topics'][1][-40:], '0x'+x['topics'][2][-40:], int(x['data'],16) if x['data'] not in ('0x','') else 0, x['transactionHash'], int(x['logIndex'],16)))
        time.sleep(0.2)
    with gzip.open(out,'wt') as f: json.dump(rows,f)
    print(out, len(rows), stats, f"{time.time()-t:.0f}s", flush=True)
if __name__=="__main__":
    a,b,out=int(sys.argv[1]),int(sys.argv[2]),sys.argv[3]
    run(a,b,out)
