import json, time, urllib.request, sys
UA={"User-Agent":"research-script/1.0","Content-Type":"application/json"}
T0="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
S=json.load(open('sets.json'))
cex=list(S['cex'].keys()); toks=list(S['toks'].keys())
def pad(a): return "0x"+"0"*24+a[2:]
def call(url, params, timeout=90):
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_getLogs","params":[params]}).encode()
    t=time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=body,headers=UA),timeout=timeout) as r:
            d=json.load(r)
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} {e.read()[:200]}", time.time()-t
    except Exception as e:
        return None, f"EXC {type(e).__name__} {str(e)[:150]}", time.time()-t
    return d.get("result"), d.get("error"), time.time()-t
