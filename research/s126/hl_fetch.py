"""s126 — фандинг Hyperliquid за 8 ч до каждого начисления сделок 🌊 (s23/rule_trades.pkl, ставка ≤ −1%): POST
api.hyperliquid.xyz/info {"type": "fundingHistory", "coin", "startTime", "endTime"}. Тикеры 1000x на HL — с приставкой k
(1000PEPE → kPEPE). Пустой ответ — монеты на HL в это время нет. Бережно: 1 запрос в секунду. Итог — s126/hl.pkl:
{(монета, T): [ставки]}; прерванный сбор продолжается. Запуск из папки с данными: python3 <repo>/research/s126/hl_fetch.py"""
import json
import os
import pickle
import time
import urllib.error
import urllib.request

import pandas as pd


def hl_name(s):
    for p, k in (("1000000", ""), ("1000", "k")):
        if s.startswith(p):
            return k + s[len(p):]
    return s


def get(body):
    for k in range(4):
        try:
            req = urllib.request.Request("https://api.hyperliquid.xyz/info", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code == 500:                                     # монеты на HL нет: ответ 500 и null
                return []
            time.sleep(5 + 10 * k)
        except Exception:
            time.sleep(5 + 10 * k)
    return None


def main():
    os.makedirs("s126", exist_ok=True)
    R = pd.read_pickle("s23/rule_trades.pkl"); R = R[R.rate <= -0.01]
    path = "s126/hl.pkl"
    out = pickle.load(open(path, "rb")) if os.path.exists(path) else {}
    n = 0
    for s, T in zip(R.s, R["T"].astype(int)):
        if (s, T) in out:
            continue
        d = get({"type": "fundingHistory", "coin": hl_name(s), "startTime": (T - 8 * 3600) * 1000, "endTime": T * 1000 - 1})
        if d is None:
            continue
        out[(s, T)] = [float(x["fundingRate"]) for x in d] if isinstance(d, list) else []
        n += 1
        if n % 100 == 0:
            pickle.dump(out, open(path, "wb")); print(n, len(out), flush=True)
        time.sleep(1.0)
    pickle.dump(out, open(path, "wb"))
    print("готово", len(out), "с данными HL:", sum(1 for v in out.values() if v), flush=True)


if __name__ == "__main__":
    main()
