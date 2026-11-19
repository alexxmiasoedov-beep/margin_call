"""s188 — посты Reddit по словам в заголовке через открытый архив Arctic Shift (reddit.com из контейнера закрыт).
Сначала одно окно на весь срок 2019–2026; если пришло 100 постов (предел) — окно делится пополам. На «Timeout»
(архив просит замедлиться) — пауза 120 с и одна повторная попытка, затем деление окна. Между запросами 30 с, после отказа архива 120 с (архив ограничивает полнотекстовый поиск).
Только публичные метаданные: id, время, заголовок, рейтинг, число комментариев, флейр, сабреддит.
Итог — /home/user/mc_data/s188/reddit/posts.jsonl (дописывается; готовые пары «сабреддит × слово» — done.txt)."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

OUT = "/home/user/mc_data/s188/reddit"
UA = {"User-Agent": "research-script/1.0"}
API = "https://arctic-shift.photon-reddit.com/api/posts/search"
PLAN = [  # (сабреддит, слова) — по убыванию важности для этапа
    ("algotrading", "borrow,lending,margin,funding,squeeze,liquidation,basis,carry,overfitting,listing,pump,korean,"
                    "upbit,open interest,lookahead,survivorship"),
    ("BitcoinMarkets", "borrow,lending,funding,squeeze,bitfinex,shorts,kimchi,upbit,liquidation,open interest,basis"),
    ("binance", "borrow,interest rate,lending,margin,funding,monitoring tag,listing"),
    ("CryptoMarkets", "borrow,funding,squeeze,upbit,listing,unlock"),
    ("CryptoCurrency", "upbit,kimchi,borrow,funding rate,short squeeze,unlock,listing pump,open interest"),
    ("defi", "borrow rate,utilization,aave"),
    ("quant", "crypto,funding,perpetual"),
    ("CryptoCurrencyTrading", "funding,borrow,squeeze,upbit,listing"),
    ("CryptoMoonShots", "upbit,binance listing"),
]
FIELDS = "id,created_utc,title,score,num_comments,subreddit,link_flair_text,author"
A0, A1 = 1546300800, int(time.time())          # 01.01.2019 — сейчас
done_path = f"{OUT}/done.txt"
done = set(open(done_path).read().split("\n")) if os.path.exists(done_path) else set()
fo = open(f"{OUT}/posts.jsonl", "a")
nreq = 0


def call(sub, word, a, b):
    """Список постов; None — архив не успел (делить окно)."""
    global nreq
    q = urllib.parse.urlencode({"subreddit": sub, "title": word, "limit": 100, "sort": "desc",
                                "after": int(a), "before": int(b), "fields": FIELDS})
    for i in range(2):
        nreq += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=120) as r:
                x = json.loads(r.read().decode())
        except Exception as e:
            print("  сеть", sub, word, e, flush=True)
            time.sleep(120)
            continue
        time.sleep(30)
        if x.get("error"):
            print("  архив:", sub, word, time.strftime('%Y-%m-%d', time.gmtime(a)), x["error"], flush=True)
            time.sleep(120)
            continue
        return x.get("data") or []
    return None


def window(sub, word, a, b):
    d = call(sub, word, a, b)
    if (d is None or len(d) >= 100) and b - a > 90 * 86400:
        m = (a + b) / 2
        return window(sub, word, a, m) + window(sub, word, m, b)
    return d or []


for sub, words in PLAN:
    for w in words.split(","):
        key = f"{sub}|{w}"
        if key in done:
            continue
        seen = set()
        for p in window(sub, w, A0, A1):
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            p["_kw"] = w
            fo.write(json.dumps(p, ensure_ascii=False) + "\n")
        fo.flush()
        open(done_path, "a").write(key + "\n")
        print(f"{sub:<22} {w:<16} постов {len(seen):>5}   запросов всего {nreq}", flush=True)
