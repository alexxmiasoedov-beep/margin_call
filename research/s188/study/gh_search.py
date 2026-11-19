"""s188 — поиск публичных репозиториев GitHub по ключевым словам через каталог awesome.ecosyste.ms (поиск GitHub
из контейнера закрыт). Только метаданные: имя, звёзды, дата последнего push, лицензия, описание, темы.
Итог — /home/user/mc_data/s188/gh_search.json и печать в лог. Код репозиториев не скачивается."""
import json
import sys
import time
import urllib.parse
import urllib.request

OUT = "/home/user/mc_data/s188/gh_search.json"
UA = {"User-Agent": "research-script/1.0"}
KW = sys.argv[1:] or [
    "funding-rate", "funding-rate-arbitrage", "margin-trading", "short-squeeze", "pump-and-dump", "pump-detection",
    "liquidation", "liquidations", "upbit", "bithumb", "kimchi-premium", "open-interest", "crypto-lending",
    "lending-bot", "new-listings", "binance-announcements", "listing-bot", "whale-alert", "smart-money",
    "market-making", "cash-and-carry", "delta-neutral", "basis-trading", "freqtrade-strategies", "crypto-sentiment",
    "borrow", "margin", "short-interest", "binance-margin", "perpetual-futures", "telegram-signals",
]


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # пауза при ошибке, без циклов вхолостую
            print("  ошибка", url, e)
            time.sleep(5 * (i + 1))
    return []


res = {}
for kw in KW:
    rows = []
    for page in (1, 2):
        url = ("https://awesome.ecosyste.ms/api/v1/projects?" +
               urllib.parse.urlencode({"keyword": kw, "per_page": 100, "page": page}))
        x = get(url)
        if not x:
            break
        for p in x:
            r = p.get("repository") or {}
            rows.append(dict(name=r.get("full_name") or p.get("url"), stars=r.get("stargazers_count") or 0,
                             pushed=(r.get("pushed_at") or "")[:10], lic=(r.get("license") or ""),
                             desc=(r.get("description") or "")[:160], topics=r.get("topics") or [],
                             archived=r.get("archived"), fork=r.get("fork")))
        if len(x) < 100:
            break
        time.sleep(1.5)
    rows.sort(key=lambda z: -z["stars"])
    res[kw] = rows
    print(f"== {kw}: {len(rows)}")
    for z in rows[:15]:
        print(f"  {z['stars']:>6} {z['name']}  {z['pushed']}  {z['lic']}  {z['desc'][:100]}")
    time.sleep(1.5)
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=0)
