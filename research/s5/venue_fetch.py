"""KuCoin / Bitget / OKX (спот к USDT): 15-мин свечи за ~25 ч до каждого пампа → s5/<площадка>/<монета>_<t>.json."""
import json, subprocess, time, re, os, sys
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
V = sys.argv[1]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
if V == "ku": L = {x["baseCurrency"] for x in json.load(open("../probe/kucoin_symbols.json"))["data"] if x["quoteCurrency"] == "USDT"}
if V == "bg": L = {x["baseCoin"] for x in json.load(open("../probe/bitget_symbols.json"))["data"] if x["quoteCoin"] == "USDT"}
if V == "okx": L = {x["baseCcy"] for x in json.load(open("../probe/okx_spot.json"))["data"] if x["quoteCcy"] == "USDT"}
URL = {"ku": lambda c, t: f"https://api.kucoin.com/api/v1/market/candles?type=15min&symbol={c}-USDT&startAt={t - 25 * 3600}&endAt={t}",
       "bg": lambda c, t: f"https://api.bitget.com/api/v2/spot/market/history-candles?symbol={c}USDT&granularity=15min&endTime={t * 1000}&limit=100",
       "okx": lambda c, t: f"https://www.okx.com/api/v5/market/history-candles?instId={c}-USDT&bar=15m&after={t * 1000}&limit=100"}[V]
P = pd.read_pickle("s2/pump_TRY.pkl"); P["c"] = P.s.map(strip); E = P[P.c.isin(L)]
def job(x):
    c, t = x; t = int(t); fn = f"s5/{V}/{c}_{t}.json"
    if os.path.exists(fn): return 0
    for k in range(6):
        r = subprocess.run(["curl", "-sS", "-m", "30", "-w", "\n%{http_code}", URL(c, t)], capture_output=True, text=True)
        body, _, code = r.stdout.rpartition("\n")
        if code == "200":
            try: j = json.loads(body)
            except Exception: j = None
            if isinstance(j, dict) and str(j.get("code")) in ("0", "200000", "00000"):
                open(fn, "w").write(json.dumps(j.get("data") or [])); return 1
            if isinstance(j, dict) and str(j.get("code")) in ("400100", "51001", "40034", "400"): open(fn, "w").write("[]"); return 2   # нет такой пары
        time.sleep(1 + 2 * k)
    return 3
jobs = sorted(set(zip(E.c, E.t)))
print(V, len(jobs), "запросов", flush=True)
res = {}
with ThreadPoolExecutor(4) as ex:
    for i, r in enumerate(ex.map(job, jobs)):
        res[r] = res.get(r, 0) + 1
        if i % 1000 == 0: print(i, res, flush=True)
print("готово", res, flush=True)
