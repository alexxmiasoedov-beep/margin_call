"""Тексты объявлений Binance о запуске фьючерсов (2024-10…2026-10): какие контракты запущены и TradFi ли они (акции, ETF,
металлы) — по тексту и заголовку. → s12/ann_perp.pkl {код: {title, ts, body}}"""
import json, time, urllib.request, pickle, re
A = pickle.load(open("s10/ann.pkl", "rb"))
sel = [a for a in A.values() if a["ts"] and a["ts"] >= 1727740800000 and re.search(r"Futures Will Launch|Pre-Market|TradFi", a["title"], re.I)]
print("объявлений:", len(sel), flush=True)
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
    j = None
    for i in range(4):
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30)); break
        except Exception:
            time.sleep(2 + 2 * i)
    if not j: continue
    body = (j.get("data") or {}).get("body") or ""
    try: body = text(json.loads(body))
    except Exception: body = re.sub(r"<[^>]+>", " ", body)
    D[a["code"]] = dict(a, body=re.sub(r"\s+", " ", body))
    time.sleep(0.25)
pickle.dump(D, open("s12/ann_perp.pkl", "wb"))
print("с текстом:", len(D), flush=True)
