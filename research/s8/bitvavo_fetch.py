"""Bitvavo (Нидерланды, евро): 15-мин свечи пары XXX-EUR за 25 ч до каждого пампа и 2 ч после → s8/bvv/<монета>_<t>.json;
курс EUR/USDT — часовые свечи спота Binance из архива → s8/eurusd.npy."""
import json, subprocess, time, re, os, io, zipfile
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
L = {x["base"] for x in json.load(open("../probe2/bitvavo_markets.json")) if x["quote"] == "EUR"}
P = pd.read_pickle("s2/pump_TRY.pkl"); P["c"] = P.s.map(strip); E = P[P.c.isin(L)]
if not os.path.exists("s8/eurusd.npy"):
    rows = []
    for y in (2024, 2025, 2026):
        for m in range(1, 13):
            ym = f"{y}-{m:02d}"
            if not ("2024-09" <= ym <= "2026-09"): continue
            r = subprocess.run(["curl", "-sS", "-m", "60", f"https://data.binance.vision/data/spot/monthly/klines/EURUSDT/1h/EURUSDT-1h-{ym}.zip"], capture_output=True)
            z = zipfile.ZipFile(io.BytesIO(r.stdout))
            for ln in z.read(z.namelist()[0]).decode().splitlines():
                p = ln.split(","); t = int(p[0]); rows.append((t // 1000000 if t > 10**14 else t // 1000, float(p[4])))
    np.save("s8/eurusd.npy", np.array(sorted(rows)))
def job(x):
    c, t = x; t = int(t); fn = f"s8/bvv/{c}_{t}.json"
    if os.path.exists(fn): return 0
    u = f"https://api.bitvavo.com/v2/{c}-EUR/candles?interval=15m&limit=120&start={(t - 25 * 3600) * 1000}&end={(t + 2 * 3600) * 1000}"
    for k in range(6):
        r = subprocess.run(["curl", "-sS", "-m", "30", "-w", "\n%{http_code}", u], capture_output=True, text=True)
        body, _, code = r.stdout.rpartition("\n")
        if code == "200": open(fn, "w").write(body); return 1
        if code in ("400", "404"): open(fn, "w").write("[]"); return 2
        time.sleep(2 + 3 * k)
    return 3
jobs = sorted(set(zip(E.c, E.t)))
print(len(jobs), "запросов", flush=True)
res = {}
with ThreadPoolExecutor(4) as ex:
    for i, r in enumerate(ex.map(job, jobs)):
        res[r] = res.get(r, 0) + 1
        if i % 1000 == 0: print(i, res, flush=True)
print("готово", res, flush=True)
