"""WhiteBIT: 15-мин свечи всех пар XXX_TRY (у монеты есть фьючерс Binance) за 10.2024–10.2026 → s8/wb/<монета>.npy
(t, закрытие, объём в лирах). API отдаёт до 1440 свечей, заканчивающихся на end; листаем назад."""
import json, subprocess, time, re, os, pickle
import numpy as np
from concurrent.futures import ThreadPoolExecutor
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb")); bases = {strip(s) for s in K} | {"USDT"}
M = [x["name"][:-4] for x in json.load(open("../probe2/wb_markets.json")) if x.get("money") == "TRY" and x["name"][:-4] in bases]
A, Z = 1727740800, int(time.time()) // 900 * 900 - 900
def get(u):
    for k in range(6):
        r = subprocess.run(["curl", "-sS", "-m", "60", u], capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            if d.get("success"): return d.get("result") or []
        except Exception: pass
        time.sleep(2 + 3 * k)
    return None
def job(c):
    fn = f"s8/wb/{c}.npy"
    if os.path.exists(fn): return c, -1
    rows, st = {}, A
    while st < Z:
        en = min(st + 1440 * 900 - 1, Z)
        r = get(f"https://whitebit.com/api/v1/public/kline?market={c}_TRY&interval=15m&start={st}&end={en}&limit=1440")
        if r is None: return c, None
        for x in r: rows[int(x[0])] = (float(x[2]), float(x[6]))
        st = en + 1
    a = np.array([(t, v[0], v[1]) for t, v in sorted(rows.items()) if A <= t <= Z]); np.save(fn, a); return c, len(a)
print(len(M), "пар", flush=True)
with ThreadPoolExecutor(6) as ex:
    for c, n in ex.map(job, M): print(c, n, flush=True)
print("готово", flush=True)
