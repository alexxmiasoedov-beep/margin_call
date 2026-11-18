import json, time, urllib.request
UA={"User-Agent":"research-script/1.0"}
out=[]
for p in range(1,7):
    url=f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={p}"
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=60) as r:
                d=json.load(r); break
        except Exception as e:
            print('retry',p,e); time.sleep(20)
    out+=d; print(p,len(d)); time.sleep(8)
json.dump(out,open('cg_markets.json','w'))
