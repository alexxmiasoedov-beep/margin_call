"""s27 — выгрузка Hyperliquid без ключей (api.hyperliquid.xyz/info), с паузами под предел 1200 веса в минуту на IP.
  python3 hl_fetch.py pf [N]        — история PnL и стоимости счёта (portfolio, perpAllTime; вес ~60) для кандидатов из
                                      рейтинга: оборот за всё время $50 млн–$5 млрд, случайный порядок (seed 1); кэш s27/pf/
  python3 hl_fetch.py fills <файл>  — сделки с 01.12.2024 (доступны последние 10 тыс.) счетов из файла адресов; кэш s27/fills/;
                                      если первые 2000 сделок уложились в 30 сут — бот-скальпер, метка <адрес>.fast
                                      [время мс, монета, сторона B/A, цена, размер, позиция до сделки, закрытый PnL, комиссия, dir]
Рейтинг — s27/leaderboard_raw.json (stats-data.hyperliquid.xyz/Mainnet/leaderboard). Запуск из папки с данными."""
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.hyperliquid.xyz/info"
BUDGET = 1050                                    # вес в минуту на все потоки (предел 1200, запас на сбои)
_lock = threading.Lock()
_next = [0.0]


def _charge(w):
    """Общий ограничитель: каждый запрос сдвигает «следующее разрешённое время» на свой вес."""
    with _lock:
        now = time.time()
        start = max(now, _next[0])
        _next[0] = start + 60 * w / BUDGET
    if start > now:
        time.sleep(start - now)


def info(body, weight, base=20):
    for i in range(6):
        _charge(base)
        try:
            req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (research)"})
            out = json.loads(urllib.request.urlopen(req, timeout=60).read())
            extra = weight(out) - base
            if extra > 0:
                _charge(extra)
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
    p = info({"type": "portfolio", "user": addr}, lambda o: 60, base=60)  # по факту ~60: при 20 — каждый второй ответ 429
    if p is None:
        return
    d = dict(p).get("perpAllTime", {})
    tmp = path + ".tmp"
    json.dump({"pnl": d.get("pnlHistory", []), "av": d.get("accountValueHistory", []), "vlm": d.get("vlm")}, open(tmp, "w"))
    os.replace(tmp, path)


START = 1733011200000                            # 01.12.2024 — сделки раньше не нужны (пулы с 01.2025)
FAST_D = 30                                      # 2000 сделок меньше чем за 30 сут — бот-скальпер: дальше не качаем


def fills(addr):
    path = f"s27/fills/{addr}.json"
    if os.path.exists(path) or os.path.exists(f"s27/fills/{addr}.fast"):
        return
    out, start = [], START
    while True:
        f = info({"type": "userFillsByTime", "user": addr, "startTime": start, "aggregateByTime": True},
                 lambda o: 20 + len(o or []) / 20)
        if f is None:
            return                                           # сбой сети — не кэшируем
        out += [[x["time"], x["coin"], x["side"], float(x["px"]), float(x["sz"]), float(x["startPosition"]),
                 float(x["closedPnl"]), float(x["fee"]), x["dir"]] for x in f]
        if len(f) < 2000:
            break
        if len(out) == 2000 and f[-1]["time"] - f[0]["time"] < FAST_D * 86400000:
            open(f"s27/fills/{addr}.fast", "w").write(str(f[0]["time"]))
            return
        start = f[-1]["time"] + 1
    tmp = path + ".tmp"
    json.dump(out, open(tmp, "w"))
    os.replace(tmp, path)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "pf":
        os.makedirs("s27/pf", exist_ok=True)
        c = candidates()[:int(sys.argv[2])] if len(sys.argv) > 2 else candidates()
        with ThreadPoolExecutor(3) as ex:
            for n, _ in enumerate(ex.map(portfolio, c)):
                if n % 500 == 0:
                    print(f"  portfolio {n}/{len(c)}", flush=True)
    elif mode == "fills":
        os.makedirs("s27/fills", exist_ok=True)
        c = [x.strip() for x in open(sys.argv[2]) if x.strip()]
        with ThreadPoolExecutor(3) as ex:
            for n, _ in enumerate(ex.map(fills, c)):
                if n % 50 == 0:
                    print(f"  fills {n}/{len(c)}", flush=True)
    print("готово", flush=True)
