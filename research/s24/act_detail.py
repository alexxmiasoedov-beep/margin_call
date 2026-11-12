"""Тексты кампаний с конкретным токеном из раздела 93 (s24/act.pkl): соревнования Alpha, турниры «Trade to Share», спотовые
и фьючерсные соревнования, «Hold X to Share». CMS detail (без ключей), пауза 0,3 с. Кэш — s24/act_text.pkl:
{код: {…, body}}. Запуск из папки с данными."""
import json
import os
import pickle
import re
import time
import urllib.request

A = pickle.load(open("s24/act.pkl", "rb"))
PAT = r"Competition|Tournament|Trade .* and Share|Trade to Share|Hold .* Share|Deposit .* Share|Challenge"
sel = [a for a in A.values() if a["ts"] and a["ts"] >= 1727740800000 and re.search(PAT, a["title"], re.I)]
PATH = "s24/act_text.pkl"
D = pickle.load(open(PATH, "rb")) if os.path.exists(PATH) else {}


def text(node):
    if isinstance(node, dict):
        out = node.get("text", "") if isinstance(node.get("text"), str) else ""
        for v in node.values():
            if isinstance(v, (list, dict)):
                out += " " + text(v)
        return out
    if isinstance(node, list):
        return " ".join(text(x) for x in node)
    return ""


print("статей для текста:", len(sel), "уже есть:", sum(a["code"] in D for a in sel), flush=True)
for n, a in enumerate(sel):
    if a["code"] in D:
        continue
    u = f"https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={a['code']}"
    j = None
    for i in range(4):
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))
            break
        except Exception:
            time.sleep(2 + 2 * i)
    if not j:
        continue
    body = (j.get("data") or {}).get("body") or ""
    try:
        body = text(json.loads(body))
    except Exception:
        body = re.sub(r"<[^>]+>", " ", body)
    D[a["code"]] = dict(a, body=re.sub(r"\s+", " ", body))
    if n % 50 == 0:
        pickle.dump(D, open(PATH, "wb"))
        print(f"  {n}/{len(sel)}", flush=True)
    time.sleep(0.3)
pickle.dump(D, open(PATH, "wb"))
print("с текстом:", len(D))
