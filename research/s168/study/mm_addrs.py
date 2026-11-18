"""s167 area A: build a market-maker / OTC address list (Ethereum) from Blockscout metadata tags (no key).
For each MM name: tags:search (name/protocol/generic), keep slugs whose tag name starts with the MM name, list addresses.
Output work/mm_addrs.json {address: tag name}"""
import json, re, time, urllib.request, urllib.parse
UA = {"User-Agent": "research-script/1.0"}
BASE = "https://metadata.services.blockscout.com/api/v1/"
def get(path, **q):
    url = BASE + path + "?" + urllib.parse.urlencode(q)
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))
        except Exception:
            time.sleep(2 + 3 * i)
    return {}
MMS = {"wintermute": r"^wintermute(?!89| exploiter)", "gsr": r"^gsr", "dwf": r"^dwf ?labs", "amber group": r"^amber", "jump trading": r"^jump (trading|crypto)",
       "jump crypto": r"^jump (trading|crypto)", "galaxy digital": r"^galaxy digital", "falconx": r"^falconx", "cumberland": r"^cumberland",
       "b2c2": r"^b2c2", "auros": r"^auros", "alameda": r"^alameda", "qcp": r"^qcp capital", "selini": r"^selini", "flow traders": r"^flow traders",
       "kairon": r"^kairon", "gotbit": r"^gotbit", "flowdesk": r"^flowdesk", "keyrock": r"^keyrock(?! governance)", "efficient frontier": r"^efficient",
       "amber": r"^amber group", "genesis trading": r"^genesis trading", "nonco": r"^nonco", "laser digital": r"^laser", "presto": r"^presto lab",
       "web3port": r"^web3port", "mantra": r"^$"}
out = {}
for name, rx in MMS.items():
    slugs = set()
    for t in ("name", "protocol", "generic"):
        d = get("tags:search", name=name, chainId=1, tag_types=t)
        for it in d.get("items", []):
            if re.search(rx, it["tag"]["name"], re.I):
                slugs.add((it["tag"]["slug"], t, it["tag"]["name"]))
        time.sleep(0.3)
    for slug, t, tname in slugs:
        tok = None
        for _ in range(20):
            q = dict(slug=slug, tagType=t, chainId=1, page_size=50)
            if tok: q["page_token"] = tok
            d = get("addresses", **q)
            for it in d.get("items", []):
                a = (it if isinstance(it, str) else (it.get("hash") or it.get("address") or "")).lower()
                if a: out.setdefault(a, tname)
            npp = d.get("next_page_params")
            if not npp: break
            tok = npp.get("page_token"); time.sleep(0.3)
        time.sleep(0.3)
    print(name, "slugs", len(slugs), "total addrs", len(out), flush=True)
json.dump(out, open("work/mm_addrs.json", "w"))
