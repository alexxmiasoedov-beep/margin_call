"""s188 — полная выгрузка постов небольших сабреддитов через архив Arctic Shift (полнотекстовый поиск архива для
активных сабреддитов не поддерживается и отвечает «Timeout», список без верхней границы времени тяжёлый).
Окна по 15 суток с границами after/before; внутри окна — страницы limit=auto (100–1000 постов) по возрастанию
времени; если архив не успевает (422/429), окно делится пополам (до 6 ч), пауза 2 с между запросами и 30–90 с
после отказа. Только публичные метаданные постов. Итог — /home/user/mc_data/s188/reddit/list_<сабреддит>.jsonl;
повторный запуск продолжает с последнего поста."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

OUT = "/home/user/mc_data/s188/reddit"
UA = {"User-Agent": "research-script/1.0"}
API = "https://arctic-shift.photon-reddit.com/api/posts/search"
SUBS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["algotrading", "BitcoinMarkets"]
A0 = int(sys.argv[2]) if len(sys.argv) > 2 else 1577836800      # 01.01.2020
FIELDS = "id,created_utc,title,score,num_comments,link_flair_text,author,subreddit"
WIN = 15 * 86400
stat = {"req": 0, "n": 0, "fail": 0}


def call(sub, a, b, tries=2):
    q = urllib.parse.urlencode({"subreddit": sub, "limit": "auto", "sort": "asc", "after": int(a), "before": int(b),
                                "fields": FIELDS})
    for i in range(tries):
        stat["req"] += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=120) as r:
                x = json.loads(r.read().decode())
            time.sleep(2)
            if x.get("error"):
                raise RuntimeError(x["error"])
            return x.get("data") or []
        except Exception as e:
            stat["fail"] += 1
            print("  архив/сеть:", sub, time.strftime('%Y-%m-%d %H:%M', time.gmtime(a)), f"{(b - a) / 3600:.0f} ч", e,
                  flush=True)
            time.sleep(30 * (i + 1))
    return None


def window(sub, a, b, fo):
    """Все посты окна [a, b); при отказе архива — половинами (не мельче 6 ч)."""
    cur = a
    while True:
        d = call(sub, cur, b)
        if d is None:
            if b - cur > 6 * 3600:
                m = (cur + b) // 2
                return window(sub, cur, m, fo) and window(sub, m, b, fo)
            return False
        for p in d:
            fo.write(json.dumps(p, ensure_ascii=False) + "\n")
        stat["n"] += len(d)
        if len(d) < 100:
            return True
        cur = max(int(p["created_utc"]) for p in d)


for sub in SUBS:
    fn = f"{OUT}/list_{sub}.jsonl"
    last = A0
    if os.path.exists(fn):
        for ln in open(fn):
            try:
                last = max(last, int(json.loads(ln)["created_utc"]))
            except Exception:
                pass
    fo = open(fn, "a")
    t0, now = time.time(), int(time.time())
    stat.update(req=0, n=0, fail=0)
    a, k, lost = last, 0, 0
    while a < now:
        b = min(a + WIN, now)
        if not window(sub, a, b, fo):
            lost += 1
            print("  пропущено окно", sub, time.strftime('%Y-%m-%d', time.gmtime(a)), flush=True)
        fo.flush()
        a = b
        k += 1
        if k % 10 == 0:
            print(f"  {sub}: {stat['n']} постов, до {time.strftime('%Y-%m-%d', time.gmtime(a))}, "
                  f"запросов {stat['req']}, отказов {stat['fail']}, {time.time() - t0:.0f} с", flush=True)
    print(f"{sub}: всего {stat['n']} постов, запросов {stat['req']}, отказов {stat['fail']}, пропущено окон {lost}",
          flush=True)
