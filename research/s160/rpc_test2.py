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
B14="0x28c6c06298d514db089934071355e5743bf21d60"; B15="0x21a31ee1afc51d94c2efccaa2092ad1028285549"; B1="0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be"
for u in sys.argv[1:]:
    r,e,dt=call(u,"eth_blockNumber",[])
    print("==",u,"head",int(r,16) if r else e, f"{dt:.1f}s")
    if not r: continue
    for (a,b,tops) in [(16000000,16000100,[T0,None,[pad(B14),pad(B15)]]),(16000000,16002000,[T0,None,[pad(B14),pad(B15)]]),(11500000,11502000,[T0,None,[pad(B1)]])]:
        r,e,dt=call(u,"eth_getLogs",[{"fromBlock":hex(a),"toBlock":hex(b),"topics":tops}])
        print(f"  {a}-{b}:", (len(r) if isinstance(r,list) else r), str(e)[:160] if e else "", f"{dt:.1f}s")
        time.sleep(0.5)
