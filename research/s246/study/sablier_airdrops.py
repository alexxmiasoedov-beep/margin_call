"""s246: кампании Sablier Airdrops (Merkle, Envio 508d217) по токенам с перпом Binance."""
import json, urllib.request, time, sys, datetime, collections
URL="https://indexer.hyperindex.xyz/508d217/v1/graphql"
def q(query, variables=None):
    body=json.dumps({"query":query,"variables":variables or {}}).encode()
    req=urllib.request.Request(URL,data=body,headers={"Content-Type":"application/json","User-Agent":"research-script/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r: return json.load(r)
pm=json.load(open('/home/user/mc_data/s160/perp_map.json'))
a2={}
for p in pm:
    for k in ('eth','bsc','base','arb'):
        a=p.get(k)
        if a and a.startswith('0x'): a2[a.lower()]=p
addrs=sorted(a2); C=[]
for i in range(0,len(addrs),100):
    r=q("""query($a:[String!]){ Campaign(where:{asset:{address:{_in:$a}}}, limit:1000){ id chainId category timestamp campaignStartTime expiration aggregateAmount claimedAmount claimedCount totalRecipients asset{address symbol decimals} } }""",{"a":addrs[i:i+100]})
    C+=r['data']['Campaign']
print("campaigns for perp tokens:",len(C))
json.dump(C,open('/home/user/mc_data/s246/sablier_campaigns.json','w'))
rows=[]
for c in C:
    p=a2[c['asset']['address'].lower()]; dec=int(c['asset']['decimals'])
    amt=int(c['aggregateAmount'])/10**dec; sh=amt/p['circ'] if p['circ'] else 0
    t=int(c['campaignStartTime'] or c['timestamp'])
    rows.append((datetime.datetime.fromtimestamp(t,datetime.UTC).strftime('%Y-%m-%d'),p['perp'],c['category'],round(sh*100,3),c['totalRecipients'],c['claimedCount']))
rows.sort()
big=[r for r in rows if r[3]>=0.5]
print("campaigns >=0.5% of current circ:",len(big))
for r in big: print(r)
