import json, time, urllib.request
UA={"User-Agent":"research-script/1.0"}
S=json.load(open('sets.json'))
out={}
for i,a in enumerate(S['toks']):
    url=f"https://eth.blockscout.com/api/v2/tokens/{a}"
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=40) as r:
                d=json.load(r); break
        except Exception as e:
            d={'err':str(e)}; time.sleep(2+2*k)
    out[a]={k:d.get(k) for k in ('symbol','decimals','total_supply','circulating_supply','exchange_rate','holders_count','err')}
    time.sleep(0.25)
json.dump(out,open('tok_meta.json','w'))
print(len(out), sum(1 for v in out.values() if v.get('decimals')))
