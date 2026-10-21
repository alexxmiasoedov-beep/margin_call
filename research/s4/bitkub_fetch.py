"""Bitkub (Таиланд, бат): полные 15-мин свечи всех пар XXX/THB, у которых есть фьючерс Binance, + USDT/THB, 01.10.2024–19.10.2026 → s4/bitkub/."""
import json, subprocess, time, pickle, re, os, sys
import numpy as np
from concurrent.futures import ThreadPoolExecutor
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb")); fut = {strip(s): s for s in K}
B = json.load(open(sys.argv[1]))["result"]
pairs = sorted({x["base_asset"] for x in B if x["quote_asset"] == "THB" and (x["base_asset"] in fut or x["base_asset"] == "USDT")})
print(len(pairs), "пар", flush=True)
A, Z, STEP = 1727740800, 1792886400, 400 * 86400
def get(u):
    for k in range(5):
        r = subprocess.run(["curl", "-sS", "-m", "90", u], capture_output=True, text=True)
        try: return json.loads(r.stdout)
        except Exception: time.sleep(2 + 3 * k)
    return None
def job(b):
    fn = f"s4/bitkub/{b}.npy"
    if os.path.exists(fn): return b, -1
    rows = []
    for fr in range(A, Z, STEP):
        j = get(f"https://api.bitkub.com/tradingview/history?symbol={b}_THB&resolution=15&from={fr}&to={min(fr + STEP, Z) - 1}")
        if j is None: return b, None
        if j.get("s") == "ok": rows += list(zip(j["t"], j["o"], j["h"], j["l"], j["c"], j["v"]))
    a = np.array(sorted(set(rows)), dtype=np.float64) if rows else np.zeros((0, 6)); np.save(fn, a); return b, len(a)
with ThreadPoolExecutor(10) as ex:
    for k, (b, n) in enumerate(ex.map(job, pairs)):
        print(k, b, n, flush=True)
