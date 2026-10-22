"""Тексты маржинальных объявлений Binance 2024–2026 (добавление пар/займов, удаление пар): CMS detail → plain text."""
import json, time, urllib.request, pickle, re, datetime
A = pickle.load(open("s10/ann.pkl", "rb"))
sel = [a for a in A.values() if a["ts"] and a["ts"] >= 1704067200000 and re.search(
    r"Removal of Margin|Margin Will Add|Margin Adds|on Cross Margin|on Isolated Margin|Margin Will Delist|Borrowable|Margin Will Remove|Margin Will Suspend|Cross Margin Pairs|Isolated Margin Pairs", a["title"], re.I)]
print("объявлений:", len(sel))
def text(node):
    if isinstance(node, dict):
        out = node.get("text", "") if isinstance(node.get("text"), str) else ""
        for v in node.values():
            if isinstance(v, (list, dict)): out += " " + text(v)
        return out
    if isinstance(node, list): return " ".join(text(x) for x in node)
    return ""
D = {}
for a in sel:
    u = f"https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={a['code']}"
    for i in range(4):
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30)); break
        except Exception:
            time.sleep(2 + 2 * i); j = None
    if not j: continue
    body = (j.get("data") or {}).get("body") or ""
    try: body = text(json.loads(body))
    except Exception: body = re.sub(r"<[^>]+>", " ", body)
    D[a["code"]] = dict(a, body=re.sub(r"\s+", " ", body))
    time.sleep(0.3)
pickle.dump(D, open("s10/ann_margin.pkl", "wb"))
print("с текстом:", len(D))
for a in sorted(D.values(), key=lambda a: a["ts"])[-3:]:
    print(datetime.datetime.utcfromtimestamp(a["ts"] / 1000), a["title"]); print("   ", a["body"][:700])
