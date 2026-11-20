"""s246: транши, клиффы и снятия (Withdraw) по потокам Sablier с депозитом >= 0,05% обращения.
Выход: /home/user/mc_data/s246/sablier_tranches.json, sablier_withdraws.json."""
import json, urllib.request, urllib.error, time, sys
URL="https://indexer.hyperindex.xyz/53b7e25/v1/graphql"
def q(query, variables=None):
    body=json.dumps({"query":query,"variables":variables or {}}).encode()
    req=urllib.request.Request(URL,data=body,headers={"Content-Type":"application/json","User-Agent":"research-script/1.0"})
    for i in range(6):
        try:
            with urllib.request.urlopen(req,timeout=120) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            print("http",e.code,e.read()[:300],file=sys.stderr,flush=True); time.sleep(10)
        except Exception as e:
            print("err",e,file=sys.stderr,flush=True); time.sleep(10)
    return None
S=json.load(open('/home/user/mc_data/s246/sablier_streams.json'))
# keep only streams with deposit >= 0.05% of current circ to limit volume
pm=json.load(open('/home/user/mc_data/s160/perp_map.json'))
a2={}
for p in pm:
    for k in ('eth','bsc','base','arb'):
        a=p.get(k)
        if a and a.startswith('0x'): a2[a.lower()]=(p['perp'],p['circ'],p['price'])
keep=[]
for s in S:
    perp,circ,price=a2[s['asset']['address'].lower()]
    dep=int(s['depositAmount'])/10**int(s['asset']['decimals'])
    if circ and dep/circ>=0.0005: keep.append(s['id'])
print("streams kept",len(keep),flush=True)
tr={}; acts=[]
for i in range(0,len(keep),25):
    chunk=keep[i:i+25]
    r=q("""query($a:[String!]){ LockupStream(where:{id:{_in:$a}}, limit:25){ id cliffAmount cliffTime initialAmount tranches(order_by:{position:asc}, limit:400){ amount endTime } segments(order_by:{position:asc}, limit:400){ amount endTime } } }""",{"a":chunk})
    if r and 'data' in r and r['data']:
        for s in r['data']['LockupStream']: tr[s['id']]=s
    else: print("tr fail",i,r and r.get('errors'),flush=True)
    off=0
    while True:
        r=q("""query($a:[String!],$o:Int){ LockupAction(where:{stream_id:{_in:$a}, category:{_eq:"Withdraw"}}, limit:1000, offset:$o, order_by:{id:asc}){ id stream_id timestamp amountB addressB } }""",{"a":chunk,"o":off})
        if not r or 'data' not in r or not r['data']: print("act fail",i,r and r.get('errors'),flush=True); break
        a=r['data']['LockupAction']; acts+=a
        if len(a)<1000: break
        off+=1000
    if i%250==0: print(i,len(tr),len(acts),flush=True)
json.dump(tr,open('/home/user/mc_data/s246/sablier_tranches.json','w'))
json.dump(acts,open('/home/user/mc_data/s246/sablier_withdraws.json','w'))
print("done",len(tr),len(acts),flush=True)
