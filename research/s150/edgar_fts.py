# EDGAR full-text search (без ключа): список фондов/компаний и дат по запросу
import json, sys, time, urllib.request, urllib.parse, collections
UA = {"User-Agent": "research-script/1.0"}
def fts(q, forms=None, start=None, end=None, page_from=0):
    p = {"q": q}
    if forms: p["forms"] = forms
    if start: p.update({"dateRange": "custom", "startdt": start, "enddt": end})
    if page_from: p["from"] = page_from
    u = "https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode(p)
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        return json.load(r)
def all_hits(q, forms=None, start=None, end=None, maxn=1000):
    out = []; f = 0
    while True:
        d = fts(q, forms, start, end, f)
        hits = d["hits"]["hits"]; out += hits
        tot = d["hits"]["total"]["value"]
        f += len(hits)
        if not hits or f >= min(tot, maxn): break
        time.sleep(0.3)
    return out, tot
if __name__ == "__main__":
    q = sys.argv[1]; forms = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    start = sys.argv[3] if len(sys.argv) > 3 else None; end = sys.argv[4] if len(sys.argv) > 4 else None
    hits, tot = all_hits(q, forms, start, end)
    print("total", tot, "got", len(hits))
    by = collections.defaultdict(list)
    for h in hits:
        s = h["_source"]
        name = (s.get("display_names") or ["?"])[0]
        by[name].append((s.get("file_date"), s.get("form") or s.get("root_forms")))
    for n, v in sorted(by.items(), key=lambda kv: min(x[0] for x in kv[1])):
        v.sort()
        print(f"{v[0][0]} .. {v[-1][0]}  n={len(v):3d}  {n[:90]}")
