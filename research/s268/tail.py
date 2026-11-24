"""s268 — докачка 15-мин свечей и фандинга после конца s224/k_d.pkl (19.11.2026 23:45) для монет, входивших в список канала
с 16.11.2026: www.binance.com/fapi (fapi.binance.com из облака отвечает 451), не больше 3 запросов в секунду.
Итог — /home/user/mc_data/s268/k_tail.pkl ({перп: {t,o,h,l,c,qv,tb,n}}) и f_tail.pkl ({перп: [[t, nan, ставка], …]}).
Запуск из /home/user/mc_data: python3 -I <repo>/research/s268/tail.py"""
import json
import pickle
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

UA = {"User-Agent": "research-script/1.0"}
API = "https://www.binance.com/fapi/v1/"
T0 = int(pd.Timestamp("2026-11-19 00:00", tz="UTC").timestamp())
_last = [0.0]


def get(path, **q):
    url = API + path + "?" + urllib.parse.urlencode(q)
    for k in range(5):
        w = _last[0] + 0.35 - time.time()
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return None
            time.sleep(5 * (k + 1))
        except Exception:  # noqa: BLE001
            time.sleep(5 * (k + 1))
    return None


def main():
    import pickle as pk
    K = pk.load(open("s224/k_d.pkl", "rb"))
    X = pd.read_pickle("s268/posts.pkl")
    syms = sorted(set(X[X.hdr >= pd.Timestamp("2026-11-16", tz="UTC")].sym))
    perps = []
    for s in syms:
        for p in (s, "1000" + s, "1000000" + s, "1M" + s):
            if p in K:
                perps.append(p); break
    print("монет в списке с 16.11:", len(syms), "с перпом в k_d:", len(perps), flush=True)
    kt, ft = {}, {}
    now = int(time.time() * 1000)
    for k, p in enumerate(perps):
        sym = p + "USDT"
        rows, st = [], T0 * 1000
        while st < now:
            d = get("klines", symbol=sym, interval="15m", startTime=st, limit=1500)
            if not d:
                break
            rows += d
            if len(d) < 1500:
                break
            st = d[-1][0] + 900_000
        if rows:
            a = np.array([[r[0] // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[7]), float(r[10]), r[8]]
                          for r in rows if r[6] < now])                       # только закрытые свечи
            kt[p] = {c: a[:, j] for j, c in enumerate(("t", "o", "h", "l", "c", "qv", "tb", "n"))}
            kt[p]["t"] = kt[p]["t"].astype(np.int64)
        f = get("fundingRate", symbol=sym, startTime=T0 * 1000, limit=1000) or []
        ft[p] = np.array([[x["fundingTime"] // 1000, np.nan, float(x["fundingRate"])] for x in f]) if f else np.zeros((0, 3))
        if k % 20 == 0:
            print(time.strftime("%H:%M:%S"), k, p, len(rows), len(f), flush=True)
    pickle.dump(kt, open("s268/k_tail.pkl", "wb")); pickle.dump(ft, open("s268/f_tail.pkl", "wb"))
    print("готово: свечей у", len(kt), "перпов; последняя свеча", max(int(v["t"][-1]) for v in kt.values()), flush=True)


if __name__ == "__main__":
    main()
