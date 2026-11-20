"""s246: доля заводов 🐋 (s160_events, 01.10.2024+) из мультисигов Safe по байткоду отправителя (селектор a619486e),
выборка 250 отправителей; RPC ethereum-rpc.publicnode.com без ключа."""
import pandas as pd, json, urllib.request, time, random, collections
d=pd.read_pickle('/home/user/mc_data/s160_events.pkl')
w=d[(d.exch=='Binance')&(d.frac>=0.005)&(d.first_clean)&(d.t>=1727740800)]
srcs=list(w.src.dropna().unique()); random.seed(1); random.shuffle(srcs); srcs=srcs[:250]
RPC="https://ethereum-rpc.publicnode.com"
def rpc(m,p):
    req=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers={"Content-Type":"application/json","User-Agent":"research-script/1.0"})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r).get('result')
kinds=collections.Counter(); safe=set()
for a in srcs:
    code=rpc("eth_getCode",[a,"latest"]) or '0x'
    if code=='0x': kinds['EOA']+=1
    elif 'a619486e' in code: kinds['Safe proxy']+=1; safe.add(a)
    elif code.startswith('0xef0100'): kinds['EIP-7702 EOA']+=1
    elif len(code)<=100: kinds['minimal proxy/other small']+=1
    else: kinds['other contract']+=1
    time.sleep(0.1)
print(dict(kinds))
sub=w[w.src.isin(srcs)]
print("events from sample:",len(sub),"from Safe:",sub.src.isin(safe).sum(), "share %.1f%%"%(100*sub.src.isin(safe).mean()))
print("tokens of Safe events:", sub[sub.src.isin(safe)].sym.value_counts().head(15).to_dict())
