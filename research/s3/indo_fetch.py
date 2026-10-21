"""Indodax (Индонезия, рупия): 15-мин свечи вокруг каждого пампа за 2 года (−3 сут … +26 ч) + курс USDT/IDR целиком → s3/indo/."""
import json, subprocess, time, datetime, pickle, re, os
import numpy as np
from concurrent.futures import ThreadPoolExecutor
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
def get(u):
    for i in range(5):
        r = subprocess.run(["curl", "-sS", "-m", "40", u], capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            if isinstance(d, list): return d
        except Exception: pass
        time.sleep(2 + 2 * i)
    return None
pairs = {x["symbol"] for x in json.loads(subprocess.run(["curl", "-sS", "-m", "40", "https://indodax.com/api/pairs"], capture_output=True, text=True).stdout)}
EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]
def job(a):
    sym, frm, to, fn = a
    if os.path.exists(fn): return 0
    d = get(f"https://indodax.com/tradingview/history_v2?symbol={sym}&tf=15&from={int(frm)}&to={int(to)}"); time.sleep(0.2)
    if d is None: return 1
    np.save(fn, np.array([(x["Time"], float(x["Close"]), float(x["Volume"])) for x in d], dtype=float).reshape(-1, 3)); return 0
jobs = []
t = datetime.datetime(2026, 10, 20, tzinfo=datetime.timezone.utc).timestamp()
while t > datetime.datetime(2024, 10, 10, tzinfo=datetime.timezone.utc).timestamp():
    jobs.append(("USDTIDR", t - 860 * 900, t, f"s3/indo/USDTIDR_{int(t)}.npy")); t -= 860 * 900
n_ev = 0
for e in EV:
    c = strip(e["s"])
    if f"{c}IDR" in pairs:
        n_ev += 1; jobs.append((f"{c}IDR", e["t_in"] - 3 * 86400, e["t_in"] + 26 * 3600, f"s3/indo/{c}_{int(e['t_in'])}.npy"))
print("пар к рупии", len(pairs), "| пампов монет с парой", n_ev, "| запросов", len(jobs), flush=True)
fails = 0
with ThreadPoolExecutor(6) as ex:
    for n, f in enumerate(ex.map(job, jobs)):
        fails += f
        if n % 1000 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), n, "сбоев", fails, flush=True)
print("готово, сбоев", fails, flush=True)
