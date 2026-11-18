import json, time, urllib.request, sys
UA={"User-Agent":"research-script/1.0","Content-Type":"application/json"}
T0="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def call(url, method, params, timeout=40):
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    t=time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=body,headers=UA),timeout=timeout) as r:
            d=json.load(r)
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} {e.read()[:150]}", time.time()-t
    except Exception as e:
        return None, f"EXC {type(e).__name__} {str(e)[:120]}", time.time()-t
    return d.get("result"), d.get("error"), time.time()-t
def pad(a): return "0x"+"0"*24+a.lower()[2:]
HW=["0x8894e0a0c962cb723c1976a4421c95949be2d4e3","0xe2fc31f816a9b94326492132018c3aecc4a93ae1","0x3c783c21a0383057d128bae431894a5c19f9cf06","0xdccf3b77da55107280bd850ea519df3705d1a75a"]
for u in sys.argv[1:]:
    r,e,dt=call(u,"eth_blockNumber",[])
    print("==",u,"head",int(r,16) if r else e, f"{dt:.1f}s")
    if not r: continue
    head=int(r,16)
    for (a,rng) in [(head-50000,1000),(30000000,1000),(30000000,5000),(10000000,1000)]:
        r2,e2,dt=call(u,"eth_getLogs",[{"fromBlock":hex(a),"toBlock":hex(a+rng),"topics":[T0,None,[pad(x) for x in HW]]}])
        print(f"  {a}+{rng}:", (len(r2) if isinstance(r2,list) else r2), str(e2)[:150] if e2 else "", f"{dt:.1f}s")
        time.sleep(0.5)
