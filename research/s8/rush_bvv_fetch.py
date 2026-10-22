"""Bitvavo: 15-мин свечи XXX-EUR за 25 ч до каждого турецкого набега (правило журнала 🇹🇷) → s8/bvr/<монета>_<t>.json."""
import json, subprocess, time, re, os, pickle
from concurrent.futures import ThreadPoolExecutor
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
L = {x["base"] for x in json.load(open("../probe2/bitvavo_markets.json")) if x["quote"] == "EUR"}
A = pickle.load(open("s8/rush_wb.pkl", "rb"))["A"]
jobs = sorted({(strip(s), int(t)) for s, t in zip(A.s, A.t) if strip(s) in L})
def job(x):
    c, t = x; fn = f"s8/bvr/{c}_{t}.json"
    if os.path.exists(fn): return 0
    u = f"https://api.bitvavo.com/v2/{c}-EUR/candles?interval=15m&limit=120&start={(t - 25 * 3600) * 1000}&end={t * 1000 - 1}"
    for k in range(6):
        r = subprocess.run(["curl", "-sS", "-m", "30", "-w", "\n%{http_code}", u], capture_output=True, text=True)
        body, _, code = r.stdout.rpartition("\n")
        if code == "200": open(fn, "w").write(body); return 1
        if code in ("400", "404"): open(fn, "w").write("[]"); return 2
        time.sleep(2 + 3 * k)
    return 3
print(len(jobs), "запросов из", len(A), "набегов", flush=True)
res = {}
with ThreadPoolExecutor(4) as ex:
    for i, r in enumerate(ex.map(job, jobs)):
        res[r] = res.get(r, 0) + 1
        if i % 200 == 0: print(i, res, flush=True)
print("готово", res, flush=True)
