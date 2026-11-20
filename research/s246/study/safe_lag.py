"""s246: для заводов 🐋 из Safe — транзакция мультисига с transfer на тот же адрес пополнения и время
от submissionDate до executionDate (api.safe.global, адрес с контрольной суммой через keccak pycryptodome)."""
import pandas as pd, json, urllib.request, urllib.error, time, random, datetime, collections
from Crypto.Hash import keccak
def cs(a):
    a=a.lower().replace('0x',''); h=keccak.new(digest_bits=256); h.update(a.encode()); hx=h.hexdigest()
    return '0x'+''.join(c.upper() if int(hx[i],16)>=8 else c for i,c in enumerate(a))
d=pd.read_pickle('/home/user/mc_data/s160_events.pkl')
w=d[(d.exch=='Binance')&(d.frac>=0.005)&(d.first_clean)&(d.t>=1727740800)]
srcs=list(w.src.dropna().unique()); random.seed(1); random.shuffle(srcs); srcs=srcs[:250]
RPC="https://ethereum-rpc.publicnode.com"
def rpc(m,p):
    req=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers={"Content-Type":"application/json","User-Agent":"research-script/1.0"})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r).get('result')
safes=[a for a in srcs if 'a619486e' in (rpc("eth_getCode",[a,"latest"]) or '')]
ev=w[w.src.isin(safes)]
print("Safe-origin events:",len(ev),"safes:",len(safes))
lags=[]; found=0; notfound=0
for a in safes:
    A=cs(a); url=f"https://api.safe.global/tx-service/eth/api/v1/safes/{A}/multisig-transactions/?executed=true&limit=100"
    txs=[]
    for page in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"research-script/1.0"}),timeout=40) as r: j=json.load(r)
        except urllib.error.HTTPError as e:
            print("http",e.code,A); break
        txs+=j['results']; url=j.get('next')
        if not url: break
        time.sleep(0.3)
    # Safe event = transfer from Safe to deposit address (frm column is the deposit address); match by block range of event: the Safe tx happens before sweep
    for _,e in ev[ev.src==a].iterrows():
        # candidate Safe txs executed within 3 days before the sweep block time
        best=None
        for t in txs:
            if not t.get('executionDate') or not t.get('submissionDate'): continue
            E=datetime.datetime.fromisoformat(t['executionDate'].replace('Z','+00:00')).timestamp()
            if 0 <= e.t - E <= 3*86400:
                dd=(t.get('dataDecoded') or {})
                to=(dd.get('parameters') or [{}])[0].get('value','') if dd.get('method')=='transfer' else ''
                if to and to.lower()==e.frm.lower():
                    S=datetime.datetime.fromisoformat(t['submissionDate'].replace('Z','+00:00')).timestamp()
                    best=(E-S)/3600; break
        if best is None: notfound+=1
        else: found+=1; lags.append(best)
    time.sleep(0.3)
import statistics
print("matched:",found,"not matched:",notfound)
if lags:
    lags.sort(); print("lead time h: median %.1f, p25 %.1f, p75 %.1f, share >=1h %.0f%%"%(statistics.median(lags),lags[len(lags)//4],lags[3*len(lags)//4],100*sum(x>=1 for x in lags)/len(lags)))
    print([round(x,1) for x in lags])
