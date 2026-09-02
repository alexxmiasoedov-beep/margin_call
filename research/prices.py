"""Parse posts.jsonl -> signals.csv; fetch 15m klines for every symbol -> klines/<SYM>.json"""
import json, re, os, sys, time, subprocess, datetime, csv

def num(s):
    s = s.strip()
    mult = {"K": 1e3, "M": 1e6, "B": 1e9}
    if s and s[-1] in mult:
        return float(s[:-1]) * mult[s[-1]]
    return float(s)

signals = []
for line in open(sys.argv[1] if len(sys.argv) > 1 else "posts.jsonl"):
    p = json.loads(line)
    if not p["ts"]:
        continue
    ts = datetime.datetime.fromisoformat(p["ts"])
    rank = 0
    for ln in p["text"].splitlines():
        m = re.match(r'^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)\s+(-?[\d.]+)\s*$', ln.strip())
        if not m:
            continue
        rank += 1
        signals.append({
            "post": p["id"], "ts": ts.isoformat(), "epoch": int(ts.timestamp()),
            "sym": m.group(1), "bor": num(m.group(2)), "rep": num(m.group(3)),
            "br": float(m.group(4)), "chng": float(m.group(5)), "rank": rank,
        })
print("signals:", len(signals), "posts:", len({s['post'] for s in signals}))
with open("signals.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(signals[0].keys()))
    w.writeheader(); w.writerows(signals)

syms = sorted({s["sym"] for s in signals})
print("symbols:", len(syms))
t0 = min(s["epoch"] for s in signals) - 3600 * 6
t1 = int(time.time())
os.makedirs("klines", exist_ok=True)

def curl(url):
    r = subprocess.run(["curl", "-sS", "-m", "30", url], capture_output=True, text=True)
    return r.stdout

def mexc(sym):
    out = []; a = t0
    while a < t1:
        b = min(a + 900 * 499, t1)
        d = curl(f"https://api.mexc.com/api/v3/klines?symbol={sym}USDT&interval=15m&startTime={a*1000}&endTime={b*1000}&limit=500")
        try:
            j = json.loads(d)
        except Exception:
            return None
        if not isinstance(j, list):
            return None
        out += [(int(k[0]) // 1000, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])) for k in j]
        a = b + 900; time.sleep(0.12)
    return sorted(set(out)) or None

def gate(sym):
    out = []; a = t0
    while a < t1:
        b = min(a + 900 * 990, t1)
        d = curl(f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={sym}_USDT&interval=15m&from={a}&to={b}")
        try:
            j = json.loads(d)
        except Exception:
            return None
        if not isinstance(j, list):
            return None
        out += [(int(k[0]), float(k[5]), float(k[3]), float(k[4]), float(k[2]), float(k[6])) for k in j]
        a = b + 900; time.sleep(0.15)
    return sorted(set(out)) or None

def kucoin(sym):
    out = []; a = t0
    while a < t1:
        b = min(a + 900 * 1490, t1)
        d = curl(f"https://api.kucoin.com/api/v1/market/candles?type=15min&symbol={sym}-USDT&startAt={a}&endAt={b}")
        try:
            j = json.loads(d)["data"]
        except Exception:
            return None
        if not j and not out:
            return None
        out += [(int(k[0]), float(k[1]), float(k[3]), float(k[4]), float(k[2]), float(k[5])) for k in j]
        a = b + 900; time.sleep(0.15)
    return sorted(set(out)) or None

srcs = {}
for s in syms:
    fn = f"klines/{s}.json"
    if os.path.exists(fn):
        srcs[s] = json.load(open(fn))["src"]; continue
    for name, fn_ in (("mexc", mexc), ("gate", gate), ("kucoin", kucoin)):
        k = fn_(s)
        if k and len(k) > 50:
            json.dump({"src": name, "k": k}, open(fn, "w"))
            srcs[s] = name
            break
        time.sleep(0.2)
    else:
        srcs[s] = None
    print(s, srcs[s], flush=True)
    time.sleep(0.15)

print("resolved:", sum(1 for v in srcs.values() if v), "missing:", [s for s, v in srcs.items() if not v])
