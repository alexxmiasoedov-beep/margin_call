"""Hourly DVOL (Deribit volatility index) for a currency, paged backwards. Usage: python3 -I dvol.py CUR OUT.json"""
import sys, json, time, urllib.request
UA = {"User-Agent": "research-script/1.0"}
def get(u):
    for k in range(6):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
        except Exception as e:
            err = e; time.sleep(2 * (k + 1))
    raise RuntimeError(err)
cur, out = sys.argv[1], sys.argv[2]
st = 1609459200000; en = int(time.time() * 1000); rows = {}; n = 0
while True:
    r = get(f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={cur}&start_timestamp={st}&end_timestamp={en}&resolution=3600")["result"]
    n += 1
    for t, o, h, l, c in r["data"]:
        rows[t] = (o, h, l, c)
    if not r.get("continuation") or not r["data"]:
        break
    en = r["continuation"]
json.dump(sorted(rows.items()), open(out, "w"))
ts = sorted(rows); gaps = [(ts[i - 1], ts[i]) for i in range(1, len(ts)) if ts[i] - ts[i - 1] > 3600_000]
import datetime as dt
U = lambda x: dt.datetime.fromtimestamp(x / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
print(cur, "requests", n, "hours", len(rows), "from", U(ts[0]), "to", U(ts[-1]), "gaps>1h", len(gaps), "max gap h", max(((b - a) / 3600_000 for a, b in gaps), default=0))
for a, b in sorted(gaps, key=lambda g: g[0] - g[1])[:5]:
    print("   gap", U(a), "->", U(b), (b - a) / 3600_000, "h")
