import json, sys, time, urllib.request, urllib.parse
UA={"User-Agent":"research-script/1.0"}
BASE="https://metadata.services.blockscout.com/api/v1/"
def get(path, **q):
    url=BASE+path+"?"+urllib.parse.urlencode(q)
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=40) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(2+3*i); err=e
    raise err
def search(name, chain, types=("name","generic")):
    out=[]
    for t in types:
        d=get("tags:search", name=name, chainId=chain, tag_types=t)
        for it in d.get("items",[]):
            out.append((t,it["tag"]["slug"],it["tag"]["name"]))
    return out
def addresses(slug, tagtype, chain, maxpages=400):
    res=[]; tok=None
    for p in range(maxpages):
        q=dict(slug=slug, tagType=tagtype, chainId=chain, page_size=50)
        if tok: q["page_token"]=tok
        d=get("addresses", **q)
        res+=d.get("items",[])
        npp=d.get("next_page_params")
        if not npp: break
        tok=npp["page_token"]
    return res
if __name__=="__main__":
    mode=sys.argv[1]
    if mode=="search":
        for n in sys.argv[3:]:
            r=search(n, sys.argv[2])
            print(n, len(r), r[:12])
    else:
        slug,tt,chain=sys.argv[2:5]
        a=addresses(slug,tt,chain)
        print(slug, chain, len(a))
        json.dump(a, open(f"labels/{slug}_{chain}.json","w"))
