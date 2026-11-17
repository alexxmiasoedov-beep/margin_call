"""s124 — объявления Binance разделов 48 (новые листинги) и 49 (новости) через публичный CMS API сайта, вся история.
Итог — s124/ann.pkl: {id: {"title", "ts" (мс), "cat"}}. Запуск из папки с данными: python3 <repo>/research/s124/ann_fetch.py"""
import json
import os
import pickle
import time
import urllib.request

URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId={}&pageNo={}&pageSize=50"


def get(url):
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(req, timeout=40).read())
        except Exception:
            time.sleep(2 + 3 * k)
    return None


def main():
    os.makedirs("s124", exist_ok=True)
    out = {}
    for cat in (48, 49):
        page = 1
        while True:
            d = get(URL.format(cat, page))
            arts = ((d or {}).get("data") or {}).get("catalogs", [{}])[0].get("articles", []) if d else []
            if not arts:
                break
            for a in arts:
                out[a.get("code") or a.get("id")] = {"title": a["title"], "ts": int(a["releaseDate"]), "cat": cat}
            page += 1
            time.sleep(0.3)
        print(f"раздел {cat}: страниц {page - 1}", flush=True)
    pickle.dump(out, open("s124/ann.pkl", "wb"))
    ts = sorted(v["ts"] for v in out.values())
    print(f"объявлений {len(out)}, с {time.strftime('%Y-%m-%d', time.gmtime(ts[0] / 1000))} по {time.strftime('%Y-%m-%d', time.gmtime(ts[-1] / 1000))}")


if __name__ == "__main__":
    main()
