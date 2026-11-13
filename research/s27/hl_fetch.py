"""s27 — выгрузка Hyperliquid без ключей (api.hyperliquid.xyz/info), с паузами под предел 1200 веса в минуту на IP.
  python3 hl_fetch.py pf [N]        — история PnL и стоимости счёта (portfolio, perpAllTime; вес 20) для кандидатов из
                                      рейтинга: оборот за всё время $50 млн–$5 млрд, случайный порядок (seed 1); кэш s27/pf/
  python3 hl_fetch.py fills <файл>  — все доступные сделки (последние 10 тыс.) счетов из файла адресов; кэш s27/fills/
                                      [время мс, монета, сторона B/A, цена, размер, позиция до сделки, закрытый PnL, комиссия, dir]
Рейтинг — s27/leaderboard_raw.json (stats-data.hyperliquid.xyz/Mainnet/leaderboard). Запуск из папки с данными."""
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

API = "https://api.hyperliquid.xyz/info"
BUDGET = 1000                                    # вес в минуту (предел 1200, запас на сбои)


def info(body, weight):
    for i in range(6):
        try:
            req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (research)"})
            out = json.loads(urllib.request.urlopen(req, timeout=60).read())
            time.sleep(60 * weight(out) / BUDGET)
            return out
        except urllib.error.HTTPError as e:
            time.sleep(60 if e.code == 429 else 5 + 5 * i)
        except Exception:
            time.sleep(5 + 5 * i)
    return None


def candidates():
    rows = json.load(open("s27/leaderboard_raw.json"))["leaderboardRows"]
    out = []
    for r in rows:
        v = float(dict(r["windowPerformances"])["allTime"]["vlm"])
        if 5e7 <= v < 5e9:
            out.append(r["ethAddress"])
    random.Random(1).shuffle(out)
    return out


def portfolio(addr):
    path = f"s27/pf/{addr}.json"
    if os.path.exists(path):
        return
    p = info({"type": "portfolio", "user": addr}, lambda o: 20)
    if p is None:
        return
    d = dict(p).get("perpAllTime", {})
    json.dump({"pnl": d.get("pnlHistory", []), "av": d.get("accountValueHistory", []), "vlm": d.get("vlm")}, open(path, "w"))


def fills(addr):
    path = f"s27/fills/{addr}.json"
    if os.path.exists(path):
        return
    out, start = [], 0
    while True:
        f = info({"type": "userFillsByTime", "user": addr, "startTime": start, "aggregateByTime": True},
                 lambda o: 20 + len(o or []) / 20)
        if f is None:
            return                                           # сбой сети — не кэшируем
        out += [[x["time"], x["coin"], x["side"], float(x["px"]), float(x["sz"]), float(x["startPosition"]),
                 float(x["closedPnl"]), float(x["fee"]), x["dir"]] for x in f]
        if len(f) < 2000:
            break
        start = f[-1]["time"] + 1
    json.dump(out, open(path, "w"))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "pf":
        os.makedirs("s27/pf", exist_ok=True)
        c = candidates()[:int(sys.argv[2])] if len(sys.argv) > 2 else candidates()
        for n, a in enumerate(c):
            portfolio(a)
            if n % 500 == 0:
                print(f"  portfolio {n}/{len(c)}", flush=True)
    elif mode == "fills":
        os.makedirs("s27/fills", exist_ok=True)
        c = [x.strip() for x in open(sys.argv[2]) if x.strip()]
        for n, a in enumerate(c):
            fills(a)
            if n % 50 == 0:
                print(f"  fills {n}/{len(c)}", flush=True)
    print("готово", flush=True)
