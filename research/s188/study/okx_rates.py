"""s188 — проба: часовая ставка займа OKX (открытый finance/savings/lending-rate-history, без ключа; история с ~01.2022)
как датчик загрузки пула там, где ставка Binance ещё администрируемая (до 02.2023). 12 оборотных монет, 01.2022–05.2023
(ETH — до 09.2024),
страницы по 100 часов назад по времени, пауза 0,35 с (предел OKX — 6 запросов в секунду), после ошибки 20–60 с.
Только ряд ставок, без доходов. Итог — /home/user/mc_data/s188/okx/<монета>.csv (время, rate, lendingRate)."""
import json
import os
import time
import urllib.request

OUT = "/home/user/mc_data/s188/okx"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "research-script/1.0"}
B = "https://www.okx.com/api/v5/finance/savings/lending-rate-history"
COINS = ["ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT", "FIL", "SAND", "APE", "CRV"]
T0 = 1640995200 * 1000          # 01.01.2022
T1 = 1685577600 * 1000          # 01.06.2023 (ETH — до 10.2024)
for c in COINS:
    fn = f"{OUT}/{c}.csv"
    if os.path.exists(fn):
        continue
    rows, after = [], T1
    while after > T0:
        x = None
        for i in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(f"{B}?ccy={c}&limit=100&after={after}",
                                                                   headers=UA), timeout=30) as r:
                    x = json.loads(r.read().decode())
                break
            except Exception as e:
                print("  ошибка", c, after, e, flush=True)
                time.sleep(20 * (i + 1))
        d = (x or {}).get("data") or []
        if not d:
            break
        for z in d:
            rows.append((int(z["ts"]) // 1000, float(z["rate"] or 0), float(z["lendingRate"] or 0)))
        after = min(int(z["ts"]) for z in d)
        time.sleep(0.35)
    rows = sorted(set(rows))
    with open(fn, "w") as f:
        for t, r, lr in rows:
            f.write(f"{t},{r},{lr}\n")
    first = time.strftime('%Y-%m-%d', time.gmtime(rows[0][0])) if rows else "—"
    print(f"{c}: {len(rows)} часов с {first}", flush=True)
