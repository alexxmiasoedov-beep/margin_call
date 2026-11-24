"""s278 — выборка часовых свечей японских бирж (без ключей): bitbank (пары к иене, свечи по суткам UTC) и GMO Coin
(спот и маржинальные пары *_JPY; сутки GMO начинаются в 06:00 JST = 21:00 UTC). Дни выборки — каждый 11-й день
01.10.2024–17.10.2026 (день недели меняется). Иена → $ по BTC/JPY bitbank и BTC перпа Binance того же часа.
Результат — /dev/shm/s278/japan/<биржа>.pkl {монета: (t начала часа, оборот $, цена $)}; кэш ответов — japan/c/.
Запуск: python3 -I fetch_japan.py (из /home/user/mc_data — нужен перп BTC из s224/k_d.pkl)."""
import datetime as dt
import json
import os
import pickle
import sys
import threading
import time
import urllib.error
import urllib.request

import numpy as np

UA = {"User-Agent": "research-script/1.0"}
ROOT = "/dev/shm/s278/japan"
D0 = dt.date(2024, 10, 1)
DAYS = [D0 + dt.timedelta(days=11 * i) for i in range(0, 69) if D0 + dt.timedelta(days=11 * i) <= dt.date(2026, 10, 17)]


def get(url):
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15 + 10 * k)
                continue
            if e.code in (400, 404):
                return None
        except Exception:
            pass
        time.sleep(2 + 3 * k)
    return "ERR"


def cached(name, url, pause):
    f = f"{ROOT}/c/{name}.json"
    if os.path.exists(f):
        return json.load(open(f))
    x = get(url)
    time.sleep(pause)
    if x == "ERR":
        return None
    json.dump(x, open(f, "w"))
    return x


def bitbank(pairs, out):
    rows = {}
    for p in pairs:
        for d in DAYS:
            ds = d.strftime("%Y%m%d")
            x = cached(f"bb_{p}_{ds}", f"https://public.bitbank.cc/{p}/candlestick/1hour/{ds}", 0.5)
            if not x or not x.get("success"):
                continue
            for c in x["data"]["candlestick"][0]["ohlcv"]:
                rows.setdefault(p, {})[int(c[5]) // 1000] = (float(c[3]), float(c[4]))   # закрытие, объём в монете
    out["bitbank"] = rows


def gmo(syms, out):
    rows = {}
    for s in syms:
        for d in DAYS:
            ds = d.strftime("%Y%m%d")
            x = cached(f"gmo_{s}_{ds}", f"https://api.coin.z.com/public/v1/klines?symbol={s}&interval=1hour&date={ds}", 0.5)
            if not x or x.get("status") != 0:
                continue
            for c in x["data"]:
                rows.setdefault(s, {})[int(c["openTime"]) // 1000] = (float(c["close"]), float(c["volume"]))
    out["gmo"] = rows


def main():
    os.makedirs(f"{ROOT}/c", exist_ok=True)
    bases = set(json.load(open("/dev/shm/s278/perps_d.json"))["base"].values())
    bb = [x["pair"] for x in get("https://public.bitbank.cc/tickers_jpy")["data"]]
    bb = [p for p in bb if p.split("_")[0].upper() in bases]
    gs = [x["symbol"] for x in get("https://api.coin.z.com/public/v1/symbols")["data"]]
    gs = [s for s in gs if s.split("_")[0] in bases]
    if "btc_jpy" not in bb:
        bb.append("btc_jpy")
    print(f"bitbank пар {len(bb)}, GMO {len(gs)}, дней {len(DAYS)}", flush=True)
    res = {}
    th = [threading.Thread(target=bitbank, args=(bb, res)), threading.Thread(target=gmo, args=(gs, res))]
    [t.start() for t in th]
    [t.join() for t in th]
    # курс иены: BTC/JPY bitbank / BTC перпа на конце часа
    K = pickle.load(open("s224/k_d.pkl", "rb"))
    a = K["BTC"]
    t = a["t"].astype(np.int64)
    end = {int(x) + 900: float(c) for x, c in zip(t, a["c"]) if (int(x) + 900) % 3600 == 0}
    rate = {h: v[0] / end[h + 3600] for h, v in res["bitbank"]["btc_jpy"].items() if h + 3600 in end}
    for ven, rows in res.items():
        out = {}
        for p, r in rows.items():
            coin = p.split("_")[0].upper()
            hs = sorted(h for h in r if h in rate)
            if not hs:
                continue
            tt = np.array(hs, np.int64)
            cl = np.array([r[h][0] for h in hs]) / np.array([rate[h] for h in hs])
            vol = np.array([r[h][0] * r[h][1] for h in hs]) / np.array([rate[h] for h in hs])
            if coin in out:                                  # GMO: спот и маржа *_JPY одной монеты — обороты складываются
                t0, v0, c0 = out[coin]
                m = dict(zip(t0.tolist(), v0.tolist()))
                for h, v in zip(hs, vol):
                    m[h] = m.get(h, 0.0) + v
                ks = sorted(m)
                cm = dict(zip(t0.tolist(), c0.tolist()))
                cm.update(dict(zip(hs, cl.tolist())))
                out[coin] = (np.array(ks, np.int64), np.array([m[h] for h in ks]), np.array([cm[h] for h in ks]))
            else:
                out[coin] = (tt, vol, cl)
        pickle.dump(out, open(f"{ROOT}/{ven}.pkl", "wb"))
        print(f"{ven}: монет {len(out)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
