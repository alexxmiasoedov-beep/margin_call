import json, time, urllib.request, sys
UA={"User-Agent":"research-script/1.0","Content-Type":"application/json"}
T0="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def call(url, method, params, timeout=40):
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    t=time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=body,headers=UA),timeout=timeout) as r:
            d=json.load(r)
    except Exception as e:
        return None, f"EXC {type(e).__name__} {str(e)[:120]}", time.time()-t
    return d.get("result"), d.get("error"), time.time()-t
def pad(a): return "0x"+"0"*24+a.lower()[2:]
LINK="0x514910771af9ca656af840dff83e8264ecf986ca"
B1="0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be"
urls=sys.argv[1:]
for u in urls:
    r,e,dt=call(u,"eth_blockNumber",[])
    print("==",u,"head",int(r,16) if r else e, f"{dt:.1f}s")
    # old range: Dec 2020, 10k blocks, LINK transfers to Binance 1 (topic2)
    for (a,b,flt) in [(11500000,11510000,True),(11500000,11502000,False),(11500000,11600000,True)]:
        q={"fromBlock":hex(a),"toBlock":hex(b),"address":LINK,"topics":[T0,None,pad(B1)] if flt else [T0]}
        r,e,dt=call(u,"eth_getLogs",[q])
        print(f"  {a}-{b} filt={flt}:", (len(r) if isinstance(r,list) else r), e if e else "", f"{dt:.1f}s")
