"""Раздел 93 объявлений Binance («Latest Activities»: соревнования, турниры, кампании с наградами) — все статьи через
публичный CMS (без ключей). Кэш — s24/act.pkl: {код: {code, title, ts (мс), cat}}. Запуск из папки с данными."""
import json
import pickle
import time
import urllib.request

URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo={p}&pageSize=50&catalogId=93"
out = {}
for p in range(1, 200):
    d = None
    for i in range(4):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(URL.format(p=p), headers={"User-Agent": "Mozilla/5.0"}), timeout=30))
            break
        except Exception:
            time.sleep(2 + 2 * i)
    arts = [a for c in ((d or {}).get("data") or {}).get("catalogs") or [] for a in c.get("articles") or []]
    if not arts:
        break
    for a in arts:
        out[a["code"]] = dict(code=a["code"], title=a.get("title", ""), ts=a.get("releaseDate"), cat=93)
    if p % 10 == 0:
        print(f"  страница {p}: статей {len(out)}", flush=True)
    time.sleep(0.3)
pickle.dump(out, open("s24/act.pkl", "wb"))
print("готово:", len(out))
