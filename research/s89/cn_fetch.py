"""s89 — оборот спота OKX и Bitget (пары к USDT) за последний полный час до закрытия свечи каждого пампа
(s15/kr_pumps.pkl; час, закончившийся не позже закрытия свечи пампа, — как у 🛒).
Пары — из текущих списков бирж; монета фьючерса 1000X / 1000000X ищется и как X.
Результат — s89/cn_vol.pkl {(фьючерс, индекс свечи пампа): {"okx": $ | 0 | None, "bitget": ...}}: 0 — пары нет или
в этот час не торговалась, None — биржа не ответила. Прерванный сбор продолжается.

Запуск из папки с данными: python3 <путь>/s89/cn_fetch.py"""
import json
import os
import pickle
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OUT = "s89/cn_vol.pkl"
H1 = 3600
LOCK = threading.Lock()


def get(url):
    for i in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "margin-call research"}), timeout=20) as r:
                x = json.loads(r.read().decode())
            if isinstance(x, dict) and str(x.get("code")) in ("50011", "429"):   # лимит запросов OKX — пауза и повтор
                raise RuntimeError("limit")
            return x
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                try:
                    return json.loads(e.read().decode())
                except Exception:
                    return {}
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return None


def bases(sym, have):
    c = [sym]
    if sym.startswith("1000000"):
        c.append(sym[7:])
    if sym.startswith("1000"):
        c.append(sym[4:])
    if sym.startswith("1M"):
        c.append(sym[2:])
    return next((b for b in c if b in have), None)


def okx(b, hs):
    x = get(f"https://www.okx.com/api/v5/market/history-candles?instId={b}-USDT&bar=1H&after={hs * 1000 + 1}&limit=1")
    time.sleep(0.35)
    if x is None:
        return None
    d = x.get("data") or []
    return float(d[0][7]) if d and int(d[0][0]) == hs * 1000 else 0.0


def bitget(b, hs):
    x = get(f"https://api.bitget.com/api/v2/spot/market/history-candles?symbol={b}USDT&granularity=1h"
            f"&endTime={(hs + H1) * 1000 - 1}&limit=1")
    time.sleep(0.2)
    if x is None:
        return None
    d = x.get("data") or []
    return float(d[-1][6]) if d and int(d[-1][0]) == hs * 1000 else 0.0


def main():
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    ok_set = {i["baseCcy"] for i in (get("https://www.okx.com/api/v5/public/instruments?instType=SPOT") or {}).get("data", [])
              if i.get("quoteCcy") == "USDT"}
    bg_set = {i["baseCoin"] for i in (get("https://api.bitget.com/api/v2/spot/public/symbols") or {}).get("data", [])
              if i.get("quoteCoin") == "USDT"}
    print(f"пар к USDT: OKX {len(ok_set)}, Bitget {len(bg_set)}", flush=True)
    res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
    jobs = []
    for s, js in PU.items():
        t = K[s]["t"]
        for j in js:
            key = (s, int(j))
            if key in res and None not in res[key].values():
                continue
            hs = int((int(t[j]) + 900) // H1 * H1 - H1)
            jobs.append((key, hs, bases(s, ok_set), bases(s, bg_set)))
    print(f"пампов к загрузке: {len(jobs)}", flush=True)
    done = [0]

    def one(job):
        key, hs, bo, bb = job
        r = {"okx": okx(bo, hs) if bo else 0.0, "bitget": bitget(bb, hs) if bb else 0.0}
        with LOCK:
            res[key] = r; done[0] += 1
            if done[0] % 500 == 0:
                pickle.dump(res, open(OUT + ".tmp", "wb")); os.replace(OUT + ".tmp", OUT)
                print(f"  {done[0]}/{len(jobs)}", flush=True)

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(one, jobs))
    pickle.dump(res, open(OUT + ".tmp", "wb")); os.replace(OUT + ".tmp", OUT)
    bad = sum(1 for v in res.values() if None in v.values())
    print(f"готово: {len(res)} пампов, без ответа биржи {bad}", flush=True)


if __name__ == "__main__":
    main()
