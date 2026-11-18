"""s167: fetch Binance CMS article bodies as plain text. Usage: python3 -I cms_detail.py <list.json> <title-regex> <outfile.json>"""
import json, re, sys, time, urllib.request
src, rx, out = sys.argv[1], re.compile(sys.argv[2], re.I), sys.argv[3]
UA = {"User-Agent": "research-script/1.0"}
def text(node):
    if isinstance(node, dict):
        if node.get("node") == "text":
            return node.get("text", "")
        sep = "\n" if node.get("tag") in ("p", "li", "tr", "h1", "h2", "h3", "h4") else " "
        return sep.join(text(c) for c in node.get("child") or []) + (sep if sep == "\n" else "")
    if isinstance(node, list):
        return " ".join(text(c) for c in node)
    return ""
arts = [a for a in json.load(open(src)) if rx.search(a["title"])]
try:
    res = json.load(open(out))
except Exception:
    res = {}
for a in arts:
    if a["code"] in res:
        continue
    u = f"https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={a['code']}"
    for i in range(4):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))["data"]
            body = d.get("body") or ""
            try:
                t = text(json.loads(body))
            except Exception:
                t = re.sub(r"<[^>]+>", " ", body)
            res[a["code"]] = dict(title=a["title"], ts=a["ts"], text=re.sub(r"[ \t]+", " ", t.replace("&nbsp;", " ")))
            break
        except Exception as e:
            time.sleep(2 + 2 * i)
    time.sleep(0.5)
json.dump(res, open(out, "w"))
print("articles", len(arts), "saved", len(res))
