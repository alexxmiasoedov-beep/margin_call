"""s39 — займы маржи OKX (`rubik/stat/margin/loan-ratio`, сутки, 180 сут, без ключа) и суточные закрытия фьючерсов Binance
(www.binance.com/fapi/v1/klines, 1d, 200 сут) для 300 самых торгуемых фьючерсов Binance (s2/k2y.pkl).
Итог — s39/okx.pkl: {"loan": {символ: [(мс, отношение)]}, "px": {символ: [(мс открытия, закрытие)]}}. Запуск из папки с данными."""
import json
import os
import pickle
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_fetch import top_binance  # noqa: E402


def get(u):
    for i in range(4):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}), timeout=40)
            return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            time.sleep(3 + 3 * i)
        except Exception:
            time.sleep(3 + 3 * i)
    return None


if __name__ == "__main__":
    out = {"loan": {}, "px": {}}
    for n, s in enumerate(top_binance()):
        base = s
        for p in ("1000000", "10000", "1000"):
            if s.startswith(p) and len(s) > len(p):
                base = s[len(p):]; break
        j = get(f"https://www.okx.com/api/v5/rubik/stat/margin/loan-ratio?ccy={base}&period=1D")
        time.sleep(0.45)                                           # rubik: 5 запросов за 2 с
        if j and j.get("code") == "0" and j.get("data"):
            out["loan"][s] = [(int(t), float(v)) for t, v in j["data"]]
        k = get(f"https://www.binance.com/fapi/v1/klines?symbol={s}USDT&interval=1d&limit=200")
        if k:
            out["px"][s] = [(int(x[0]), float(x[4])) for x in k]
        if n % 50 == 0:
            print(f"  {n}: займов OKX {len(out['loan'])}, цен {len(out['px'])}", flush=True)
            pickle.dump(out, open("s39/okx.pkl", "wb"))
    pickle.dump(out, open("s39/okx.pkl", "wb"))
    print(f"готово: монет с займами OKX {len(out['loan'])}, с ценами {len(out['px'])}")
