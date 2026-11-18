"""s167: Blockscout metadata service (no key) — search tag slugs and list addresses per slug for chain 1.
Usage: python3 -I bs_tags.py search <name>...   |   python3 -I bs_tags.py list <slug> <tagType> <out.json>"""
import json, sys, time, urllib.request, urllib.parse
UA = {"User-Agent": "research-script/1.0"}
BASE = "https://metadata.services.blockscout.com/api/v1/"
def get(path, **q):
    url = BASE + path + "?" + urllib.parse.urlencode(q)
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as e:
            err = e; time.sleep(2 + 3 * i)
    raise err
if sys.argv[1] == "search":
    for n in sys.argv[2:]:
        out = []
        for t in ("name", "generic", "protocol"):
            d = get("tags:search", name=n, chainId=1, tag_types=t)
            out += [(t, it["tag"]["slug"], it["tag"]["name"]) for it in d.get("items", [])]
            time.sleep(0.3)
        print(n, len(out), out[:15], flush=True)
else:
    slug, tt, outp = sys.argv[2:5]; res = []; tok = None
    for p in range(400):
        q = dict(slug=slug, tagType=tt, chainId=1, page_size=50)
        if tok: q["page_token"] = tok
        d = get("addresses", **q); res += d.get("items", [])
        npp = d.get("next_page_params")
        if not npp: break
        tok = npp["page_token"]; time.sleep(0.3)
    json.dump(res, open(outp, "w")); print(slug, tt, len(res))
