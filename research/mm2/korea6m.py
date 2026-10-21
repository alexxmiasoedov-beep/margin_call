"""Корейские 15-мин свечи вокруг каждого пампа за 6,5 месяца (−24 ч … +26 ч от входа) + курс KRW-USDT за весь период → mm2/korea6/."""
import json, subprocess, time, datetime, pickle, re, os
import numpy as np
from concurrent.futures import ThreadPoolExecutor
UTC = datetime.timezone.utc; KST = datetime.timezone(datetime.timedelta(hours=9))
K = pickle.load(open("kaia/k15_6m.pkl", "rb")); EV = pickle.load(open("mm2/pumps6m.pkl", "rb"))
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
def get(u):
    for i in range(5):
        r = subprocess.run(["curl", "-sS", "-m", "30", u], capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            if isinstance(d, list): return d
        except Exception: pass
        time.sleep(1 + i)
    return None
EXS = {"upbit": ("https://api.upbit.com", UTC), "bithumb": ("https://api.bithumb.com", KST)}
MK = {ex: {x["market"][4:] for x in get(f"{b}/v1/market/all") or [] if x["market"].startswith("KRW-")} for ex, (b, tz) in EXS.items()}
def page(ex, c, to):
    b, tz = EXS[ex]; q = datetime.datetime.fromtimestamp(to, UTC).astimezone(tz).strftime("%Y-%m-%dT%H:%M:%S") + ("Z" if tz is UTC else "")
    d = get(f"{b}/v1/candles/minutes/15?market=KRW-{c}&to={q}&count=200") or []
    return [(int(datetime.datetime.fromisoformat(x["candle_date_time_utc"]).replace(tzinfo=UTC).timestamp()), x["opening_price"], x["high_price"],
             x["low_price"], x["trade_price"], float(x["candle_acc_trade_price"])) for x in d]
def job(a):
    ex, c, to = a; fn = f"mm2/korea6/{ex}_{c}_{int(to)}.npy"
    if os.path.exists(fn): return
    rows = page(ex, c, to); time.sleep(0.3)
    np.save(fn, np.array(sorted(rows), dtype=float).reshape(-1, 6))
jobs = []
for ex in EXS:
    t, end = datetime.datetime(2026, 3, 30, tzinfo=UTC).timestamp(), datetime.datetime(2026, 10, 20, tzinfo=UTC).timestamp()
    while t < end: t += 200 * 900; jobs.append((ex, "USDT", t))
for s, j, i in EV:
    c = strip(s); t_in = K[s][j, 0] + 900
    for ex in EXS:
        if c in MK[ex]: jobs.append((ex, c, t_in + 26 * 3600))
print("запросов", len(jobs), flush=True)
with ThreadPoolExecutor(8) as pool:
    for n, _ in enumerate(pool.map(job, jobs)):
        if n % 500 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), n, flush=True)
print("готово", flush=True)
