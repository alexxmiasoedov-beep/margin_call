"""s246: потоки Sablier Lockup (Envio, без ключа) для токенов с перпом Binance.
Вход: /home/user/mc_data/s160/perp_map.json (адреса eth/bsc/base/arb). Выход: /home/user/mc_data/s246/sablier_streams.json."""
import json, urllib.request, time, sys, collections
URL="https://indexer.hyperindex.xyz/53b7e25/v1/graphql"
def q(query, variables=None):
    body=json.dumps({"query":query,"variables":variables or {}}).encode()
    req=urllib.request.Request(URL,data=body,headers={"Content-Type":"application/json","User-Agent":"research-script/1.0"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req,timeout=90) as r: return json.load(r)
        except Exception as e:
            print("err",e,file=sys.stderr); time.sleep(5)
    raise SystemExit("fail")
pm=json.load(open('/home/user/mc_data/s160/perp_map.json'))
addr2perp={}
for p in pm:
    for k in ('eth','bsc','base','arb'):
        a=p.get(k)
        if a and a.startswith('0x'): addr2perp[a.lower()]=(p['perp'],p['circ'],p['price'])
addrs=sorted(addr2perp)
print("perp token addrs (EVM):",len(addrs))
# fetch streams for these assets
streams=[]
for i in range(0,len(addrs),100):
    chunk=addrs[i:i+100]; off=0
    while True:
        r=q("""query($a:[String!],$o:Int){ LockupStream(where:{asset:{address:{_in:$a}}}, limit:1000, offset:$o, order_by:{id:asc}){ id chainId asset{address symbol decimals} sender recipient depositAmount startTime endTime cliffTime shape category withdrawnAmount canceled } }""",{"a":chunk,"o":off})
        if 'errors' in r: print(r['errors'][:2]); break
        s=r['data']['LockupStream']; streams+=s
        if len(s)<1000: break
        off+=1000
print("streams:",len(streams))
json.dump(streams,open('/home/user/mc_data/s246/sablier_streams.json','w'))
