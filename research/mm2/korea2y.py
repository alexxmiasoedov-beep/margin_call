"""Корея за два года: курс KRW-USDT (Upbit, Bithumb) целиком и 15-мин свечи вокруг каждого пампа (−24 ч … +26 ч от входа)
для монет, которые сейчас торгуются на бирже (по снятым с торгов биржи историю не отдают) → mm2/korea2y/."""
import json, subprocess, time, datetime, pickle, re, os, sys, shutil
import numpy as np
from concurrent.futures import ThreadPoolExecutor
UTC = datetime.timezone.utc; KST = datetime.timezone(datetime.timedelta(hours=9))
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
def get(u):
    for i in range(6):
        r = subprocess.run(["curl", "-sS", "-m", "30", u], capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            if isinstance(d, list): return d
        except Exception: pass
        time.sleep(1 + 2 * i)
    return None
EXS = {"upbit": ("https://api.upbit.com", UTC), "bithumb": ("https://api.bithumb.com", KST)}
def page(ex, c, to):
    b, tz = EXS[ex]; q = datetime.datetime.fromtimestamp(to, UTC).astimezone(tz).strftime("%Y-%m-%dT%H:%M:%S") + ("Z" if tz is UTC else "")
    d = get(f"{b}/v1/candles/minutes/15?market=KRW-{c}&to={q}&count=200")
    if d is None: return None
    return [(int(datetime.datetime.fromisoformat(x["candle_date_time_utc"]).replace(tzinfo=UTC).timestamp()), x["opening_price"], x["high_price"],
             x["low_price"], x["trade_price"], float(x["candle_acc_trade_price"])) for x in d]
def job(a):
    ex, c, to = a; fn = f"mm2/korea2y/{ex}_{c}_{int(to)}.npy"
    if os.path.exists(fn): return 0
    old = f"mm2/korea6/{ex}_{c}_{int(to)}.npy"
    if os.path.exists(old): shutil.copy(old, fn); return 0
    rows = page(ex, c, to); time.sleep(0.3)
    if rows is None: return 1                                     # сбой — не сохраняем, перезапуск докачает
    np.save(fn, np.array(sorted(rows), dtype=float).reshape(-1, 6)); return 0
jobs = []
for ex in EXS:
    t, end = datetime.datetime(2024, 10, 15, tzinfo=UTC).timestamp(), datetime.datetime(2026, 10, 20, tzinfo=UTC).timestamp()
    while t < end: t += 200 * 900; jobs.append((ex, "USDT", t))
if len(sys.argv) > 1 and sys.argv[1] == "pumps":
    MK = {ex: {x["market"][4:] for x in get(f"{b}/v1/market/all") or [] if x["market"].startswith("KRW-")} for ex, (b, tz) in EXS.items()}
    print("KRW-рынков сейчас:", {ex: len(v) for ex, v in MK.items()}, flush=True)
    EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]
    for e in EV:
        c = strip(e["s"])
        for ex in EXS:
            if c in MK[ex]: jobs.append((ex, c, e["t_in"] + 26 * 3600))
print("запросов", len(jobs), flush=True)
fails = 0
with ThreadPoolExecutor(8) as pool:
    for n, f in enumerate(pool.map(job, jobs)):
        fails += f
        if n % 1000 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), n, "сбоев", fails, flush=True)
print("готово, сбоев", fails, flush=True)
