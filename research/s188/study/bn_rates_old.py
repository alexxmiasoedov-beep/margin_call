"""s188 — проба глубины истории ставок займа маржи Binance (публичный bapi vip/spec/history-interest-rate, без ключа,
окна по 31 сутки; s11 скачивал только с 09.2024). До ~06.2023 ряд дневной, позже — часовые изменения. Берутся
60 самых оборотных перпов периодов 10.2020–09.2022 и 10.2022–09.2024, у которых есть маржа (файл в s11/rates).
Только ряд ставок, без доходов. Итог — /home/user/mc_data/s188/bnrates/<монета>.csv (время, дневная ставка).
Пауза 0,6 с, после ошибки 20–60 с."""
import json
import os
import sys
import time
import urllib.request

import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

OUT = "/home/user/mc_data/s188/bnrates"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "research-script/1.0"}
B = "https://www.binance.com/bapi/margin/v1/public/margin/vip/spec/history-interest-rate"
have = {f[:-4] for f in os.listdir("/home/user/mc_data/s11/rates")}
tv = {}
for per in ("2020–2022", "2022–2024"):
    d = pd.read_pickle(f"{C.OUT}/daily_{per}.pkl")
    for s, v in d.groupby("s").qv.sum().items():
        tv[s] = tv.get(s, 0) + v
coins = [s for s, _ in sorted(tv.items(), key=lambda z: -z[1]) if s in have and s not in C.bad_set()][:60]
print("монет:", len(coins), ", ".join(coins), flush=True)
t0, t1 = C.ts("2020-09-01"), C.ts("2024-10-01")
for c in coins:
    fn = f"{OUT}/{c}.csv"
    if os.path.exists(fn):
        continue
    rows, a = [], t0
    while a < t1:
        b = min(a + 31 * 86400 - 1, t1)
        x = None
        for i in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(
                        f"{B}?asset={c}&vipLevel=0&startTime={a * 1000}&endTime={b * 1000}", headers=UA),
                        timeout=30) as r:
                    x = json.loads(r.read().decode())
                break
            except Exception as e:
                print("  ошибка", c, a, e, flush=True)
                time.sleep(20 * (i + 1))
        for z in (x or {}).get("data") or []:
            rows.append((int(z["timestamp"]) // 1000, float(z["dailyInterestRate"])))
        a = b + 1
        time.sleep(0.6)
    rows = sorted(set(rows))
    with open(fn, "w") as f:
        for t, r in rows:
            f.write(f"{t},{r}\n")
    first = time.strftime('%Y-%m-%d', time.gmtime(rows[0][0])) if rows else "—"
    print(f"{c}: {len(rows)} записей с {first}", flush=True)
