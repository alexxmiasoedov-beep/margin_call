import sys, collections
sys.path.insert(0, sys.argv[1])
from edgar_fts import all_hits
q = sys.argv[2]; forms = sys.argv[3]; s0 = sys.argv[4]; s1 = sys.argv[5]
hits, tot = all_hits(q, forms, s0, s1, maxn=300)
print(q, forms, s0, s1, "total", tot)
seen = set()
for h in sorted(hits, key=lambda h: h["_source"]["file_date"]):
    s = h["_source"]; n = (s.get("display_names") or ["?"])[0][:55]
    k = (s["file_date"], n)
    if k in seen: continue
    seen.add(k)
    print(f"  {s['file_date']}  {n}  {s.get('items') or ''}")
