import sys, collections, json
sys.path.insert(0, sys.argv[1])
from edgar_fts import all_hits
q = sys.argv[2]; forms = sys.argv[3]
hits, tot = all_hits(q, forms, "2025-01-01", "2026-11-18", maxn=2000)
by_m = collections.Counter(); names = collections.Counter()
for h in hits:
    s = h["_source"]; by_m[s["file_date"][:7]] += 1
    names[(s.get("display_names") or ["?"])[0][:60]] += 1
print(q, forms, "total", tot, "got", len(hits))
print(" ".join(f"{k[2:]}:{v}" for k, v in sorted(by_m.items())))
print("компаний:", len(names), "| топ:", "; ".join(f"{n} ({c})" for n, c in names.most_common(12)))
