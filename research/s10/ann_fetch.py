"""Объявления Binance (CMS API сайта): все статьи разделов «Latest Binance News» (49), «New Cryptocurrency Listing» (48),
«Delisting» (161) — код, заголовок, время публикации. → s10/ann.pkl"""
import json, time, urllib.request, pickle
def get(cat, page, size=50):
    u = f"https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId={cat}&pageNo={page}&pageSize={size}"
    for i in range(4):
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))
            return j["data"]
        except Exception as e:
            time.sleep(2 + 2 * i)
    return None
out = {}
for cat in (49, 48, 161):
    d = get(cat, 1); tot = d.get("total", 0); n = 0
    for page in range(1, tot // 50 + 2):
        d = get(cat, page)
        if not d: print("сбой", cat, page); continue
        arts = d.get("articles") or []
        for a in arts:
            out[a["code"]] = dict(cat=cat, code=a["code"], title=a["title"], ts=a.get("releaseDate"))
        n += len(arts)
        time.sleep(0.3)
    print(f"раздел {cat}: всего {tot}, получено {n}", flush=True)
pickle.dump(out, open("s10/ann.pkl", "wb"))
print("статей:", len(out))
