"""15-мин свечи KRW-рынков Upbit и Bithumb за 17.09–19.10 для монет с фьючерсом Binance (+ KRW-USDT для курса) → mm2/korea.pkl."""
import json, subprocess, time, datetime, pickle, re, threading, os
from concurrent.futures import ThreadPoolExecutor
import numpy as np
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
UTC = datetime.timezone.utc; KST = datetime.timezone(datetime.timedelta(hours=9))
START = datetime.datetime(2026, 9, 17, tzinfo=UTC); END = datetime.datetime(2026, 10, 19, tzinfo=UTC)
def get(u):
    for i in range(5):
        r = subprocess.run(["curl", "-sS", "-m", "30", u], capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            if isinstance(d, list): return d
        except Exception: pass
        time.sleep(1 + i)
    return None
def markets(base):
    return {x["market"][4:] for x in get(f"{base}/v1/market/all") or [] if x["market"].startswith("KRW-")}
fut = {re.sub(r"^(1000000|100000|10000|1000)", "", s): s for s in K}
OUT = {}
def run(ex, base, tz, pause):
    mk = markets(base); coins = sorted(c for c in mk if c in fut) + ["USDT"]
    print(ex, "KRW-рынков", len(mk), "с фьючерсом Binance", len(coins) - 1, flush=True)
    res = {}
    def one(c):
        fn = f"mm2/korea/{ex}_{c}.npy"
        if os.path.exists(fn): return c, np.load(fn)
        rows, to = {}, END
        while to > START:
            q = to.astimezone(tz).strftime("%Y-%m-%dT%H:%M:%S") + ("Z" if tz is UTC else "")
            d = get(f"{base}/v1/candles/minutes/15?market=KRW-{c}&to={q}&count=200"); time.sleep(pause)
            if not d: break
            for x in d:
                t = int(datetime.datetime.fromisoformat(x["candle_date_time_utc"]).replace(tzinfo=UTC).timestamp())
                rows[t] = (t, x["opening_price"], x["high_price"], x["low_price"], x["trade_price"], float(x["candle_acc_trade_price"]))
            first = min(datetime.datetime.fromisoformat(x["candle_date_time_utc"]).replace(tzinfo=UTC) for x in d)
            if first >= to or len(d) < 200: break
            to = first
        a = np.array([rows[t] for t in sorted(rows)], dtype=float).reshape(-1, 6); np.save(fn, a); return c, a
    with ThreadPoolExecutor(4) as pool:
        for n, (c, a) in enumerate(pool.map(one, coins)):
            if len(a): res[c] = a
            if n % 40 == 0: print(ex, n, c, len(a), flush=True)
    OUT[ex] = res
th = [threading.Thread(target=run, args=a) for a in (("upbit", "https://api.upbit.com", UTC, 0.35), ("bithumb", "https://api.bithumb.com", KST, 0.25))]
for x in th: x.start()
for x in th: x.join()
OUT["fut_name"] = fut
pickle.dump(OUT, open("mm2/korea.pkl", "wb")); print("готово", {k: len(v) for k, v in OUT.items()}, flush=True)
