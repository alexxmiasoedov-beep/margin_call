"""s190 Г1 — докачка часовой ставки займа маржи Binance за 01.2023–09.2024 для всех активов маржи (s11/rates) с перпом
в периоде 2022–2024 (публичный bapi vip/spec/history-interest-rate, без ключа, окна по 31 сут; логика запроса — как
s188/study/bn_rates_old.py). Итог — /home/user/mc_data/s190/rates/<актив>.csv (время, дневная ставка).
Пауза 0,6 с, после ошибки 20–60 с. Ключ --rev — тот же список в обратном порядке (второй процесс параллельно)."""
import json
import os
import pickle
import sys
import time
import urllib.request

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

OUT = "/home/user/mc_data/s190/rates"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "research-script/1.0"}
B = "https://www.binance.com/bapi/margin/v1/public/margin/vip/spec/history-interest-rate"
have = {f[:-4] for f in os.listdir("/home/user/mc_data/s11/rates")}
F = pickle.load(open("/home/user/mc_data/s117/fund_oos.pkl", "rb"))        # перпы 2022–2024
bases = {C.base(k) for k in F} - C.bad_set() - {"BTC", "ETH"}
coins = sorted(have & bases)
print("активов:", len(coins), flush=True)
t0, t1 = C.ts("2023-01-01"), C.ts("2024-10-01")
for c in (coins[::-1] if "--rev" in sys.argv else coins):
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
    if os.path.exists(fn):
        continue
    rows = sorted(set(rows))
    with open(fn + ".tmp", "w") as f:
        for t, r in rows:
            f.write(f"{t},{r}\n")
    os.replace(fn + ".tmp", fn)
    print(f"{c}: {len(rows)} записей", flush=True)
