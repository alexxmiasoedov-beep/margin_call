"""s188 — займы и маржинальные позиции Bitfinex (открытый API без ключа): часовые лонги и шорты маржи по парам
(stats1 pos.size, с 02.2021) и дневные свечи ставки займа монеты (candles trade:1D:f<монета>:a30:p2:p30 — рынок
займа, из которого берут монеты под шорт). Только запись рядов, без доходов.
Итог — /home/user/mc_data/s188/bfx/<пара>_<сторона>.json, funding_<монета>.json; лог — печать.
Предел API stats — 15 запросов в минуту: пауза 4,5 с, после ошибки 30–60 с."""
import json
import os
import time
import urllib.request

OUT = "/home/user/mc_data/s188/bfx"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "research-script/1.0"}
B = "https://api-pub.bitfinex.com/v2"
T0 = 1609459200000          # 2021-01-01: часовые pos.size начинаются с 22.02.2021
T1 = int(time.time() * 1000)


def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                x = json.loads(r.read().decode())
            time.sleep(4.5)
            return x
        except Exception as e:
            print("  ошибка", url[-80:], e, flush=True)
            time.sleep(30 * (i + 1))
    return None


# 1) кандидаты: все пары к USD/UST на бирже; признак маржи — есть ли ряд pos.size (по одному запросу на пару)
pairs = get(f"{B}/conf/pub:list:pair:exchange")[0]
margin_now = set(get(f"{B}/conf/pub:list:pair:margin")[0])
cand = sorted({p for p in pairs if (p.endswith("USD") or p.endswith(":USD")) and "TEST" not in p})
print("пар к USD:", len(cand), "сейчас с маржой:", len(margin_now), flush=True)
found = []
for p in cand:
    x = get(f"{B}/stats1/pos.size:1h:t{p}:short/hist?limit=1&sort=1")
    if x:
        found.append(p)
        print(f"  {p}: шорты с {time.strftime('%Y-%m-%d', time.gmtime(x[0][0] / 1000))}", flush=True)
json.dump(found, open(f"{OUT}/pairs.json", "w"))

# 2) часовые ряды лонгов и шортов, кусками по 10 000 часов
for p in found:
    for side in ("long", "short"):
        fn = f"{OUT}/{p.replace(':', '')}_{side}.json"
        if os.path.exists(fn):
            continue
        rows, start = [], T0
        while start < T1:
            x = get(f"{B}/stats1/pos.size:1h:t{p}:{side}/hist?limit=10000&sort=1&start={start}&end={T1}")
            if not x:
                break
            rows += x
            if len(x) < 10000:
                break
            start = x[-1][0] + 1
        json.dump(rows, open(fn, "w"))
        print(f"{p} {side}: {len(rows)} часов", flush=True)

# 3) дневные свечи ставки займа монеты (рынок funding Bitfinex)
coins = sorted({p.replace(":USD", "").replace("USD", "") for p in found})
for c in coins:
    fn = f"{OUT}/funding_{c}.json"
    if os.path.exists(fn):
        continue
    x = get(f"{B}/candles/trade:1D:f{c}:a30:p2:p30/hist?limit=10000&sort=1&start={T0 - 400 * 86400000}")
    json.dump(x or [], open(fn, "w"))
    print(f"funding {c}: {len(x or [])} сут", flush=True)
