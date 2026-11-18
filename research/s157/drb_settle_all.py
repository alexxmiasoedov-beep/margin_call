"""Page Deribit public get_last_settlements_by_currency without a type filter until a cutoff date.
Usage: python3 -I drb_settle_all.py CUR OUTFILE STOP_YYYY-MM-DD"""
import sys, json, time, urllib.request, datetime as dt
UA = {"User-Agent": "research-script/1.0"}
def get(u, tries=6):
    for k in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
        except Exception as e:
            err = e; time.sleep(2 * (k + 1))
    raise RuntimeError(f"{u}: {err}")
cur, out, stop = sys.argv[1], sys.argv[2], sys.argv[3]
stop_ms = int(dt.datetime.fromisoformat(stop).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
cont = None; allr = []
while True:
    u = f"https://www.deribit.com/api/v2/public/get_last_settlements_by_currency?currency={cur}&count=1000" + (f"&continuation={cont}" if cont else "")
    r = get(u)["result"]; s = r["settlements"]; allr += s; cont = r.get("continuation")
    if not s or not cont or cont == "none" or s[-1]["timestamp"] < stop_ms:
        break
json.dump(allr, open(out, "w"))
import collections
c = collections.Counter((x["type"], dt.datetime.fromtimestamp(x["timestamp"] / 1000, dt.timezone.utc).strftime("%Y-%m")) for x in allr)
for k in sorted(c, key=lambda z: (z[1], z[0])): print(k, c[k])
