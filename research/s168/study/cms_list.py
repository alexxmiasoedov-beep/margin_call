"""s167: list Binance CMS catalog articles with release dates. Usage: python3 -I cms_list.py <catalogId> <outdir>"""
import json, sys, time, urllib.request
cat, out = sys.argv[1], sys.argv[2]
UA = {"User-Agent": "research-script/1.0"}
def get(page, size=50):
    u = f"https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId={cat}&pageNo={page}&pageSize={size}"
    for i in range(4):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))["data"]["catalogs"][0]
            return d
        except Exception as e:
            err = e; time.sleep(2 + 2 * i)
    print("fail", page, err); return None
d = get(1); tot = d.get("total", 0); arts = []
print("catalog", cat, d.get("catalogName"), "total", tot, flush=True)
for page in range(1, tot // 50 + 2):
    d = get(page)
    if not d: continue
    arts += [dict(id=a["id"], code=a["code"], title=a["title"], ts=a.get("releaseDate")) for a in d.get("articles") or []]
    time.sleep(0.4)
json.dump(arts, open(f"{out}/cat{cat}.json", "w"))
print("got", len(arts), "with ts", sum(1 for a in arts if a["ts"]))
