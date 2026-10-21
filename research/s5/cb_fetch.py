"""Coinbase (США): 15-мин свечи пары XXX-USD за 25 ч до каждого пампа (и 2 ч после) → s5/cb/<монета>_<t>.json."""
import json, subprocess, time, pickle, re, os, sys, datetime
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
cb = json.load(open("../probe/cb_products.json")); CB = {x["base_currency"] for x in cb if x["quote_currency"] == "USD"}
P = pd.read_pickle("s2/pump_TRY.pkl"); P["c"] = P.s.map(strip); E = P[P.c.isin(CB)]
iso = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def job(x):
    c, t = x; fn = f"s5/cb/{c}_{int(t)}.json"
    if os.path.exists(fn): return 0
    u = f"https://api.exchange.coinbase.com/products/{c}-USD/candles?granularity=900&start={iso(t - 25 * 3600)}&end={iso(t + 2 * 3600)}"
    for k in range(6):
        r = subprocess.run(["curl", "-sS", "-m", "30", "-w", "\n%{http_code}", u], capture_output=True, text=True)
        body, _, code = r.stdout.rpartition("\n")
        if code == "200": open(fn, "w").write(body); return 1
        if code == "404" or "NotFound" in body: open(fn, "w").write("[]"); return 2
        time.sleep(1 + 2 * k)
    return 3
jobs = sorted(set(zip(E.c, E.t)))
print(len(jobs), "запросов", flush=True)
res = {}
with ThreadPoolExecutor(6) as ex:
    for i, r in enumerate(ex.map(job, jobs)):
        res[r] = res.get(r, 0) + 1
        if i % 500 == 0: print(i, res, flush=True)
print("готово", res, flush=True)
