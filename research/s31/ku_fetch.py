"""s31 — объявления KuCoin (публичный API /api/v3/announcements, по 30 сут с 01.09.2024): типы new-listings и delistings.
Итог — s31/ku_ann.json: [{id, t (мс), types, title}]. Запуск из папки с данными."""
import datetime
import json
import os
import time
import urllib.request

U = "https://api.kucoin.com/api/v3/announcements?annType={typ}&pageSize=50&currentPage={page}&lang=en_US&startTime={a}&endTime={b}"
T0 = int(datetime.datetime(2024, 9, 1, tzinfo=datetime.timezone.utc).timestamp() * 1000)
T1 = int(time.time() * 1000)
STEP = 30 * 86400000


def get(url):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research"}), timeout=30) as r:
                d = json.loads(r.read().decode())
                if d.get("code") == "200000":
                    return d["data"]
        except Exception:
            pass
        time.sleep(3 + 3 * i)
    return None


if __name__ == "__main__":
    out = {}
    for typ in ("new-listings", "delistings"):
        for a in range(T0, T1, STEP):
            page = 1
            while True:
                d = get(U.format(typ=typ, page=page, a=a, b=min(a + STEP, T1)))
                if d is None:
                    print("сбой", typ, a, page, flush=True); break
                for x in d.get("items", []):
                    out[x["annId"]] = dict(id=x["annId"], t=x["cTime"], types=x.get("annType"), title=x["annTitle"])
                if page >= (d.get("totalPage") or 1):
                    break
                page += 1
                time.sleep(0.3)
            time.sleep(0.3)
        print(typ, "собрано всего", len(out), flush=True)
    json.dump(sorted(out.values(), key=lambda x: x["t"]), open("s31/ku_ann.json", "w"), ensure_ascii=False)
