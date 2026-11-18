"""Page through Deribit public get_last_settlements_by_currency (type={TYPE}) to the start.
Usage: python3 -I drb_settle.py CUR OUTFILE [maxpages]"""
import sys, json, time, urllib.request, datetime as dt
UA = {"User-Agent": "research-script/1.0"}
def get(u, tries=6):
    for k in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
        except Exception as e:
            err = e; time.sleep(2 * (k + 1))
    raise RuntimeError(f"{u}: {err}")
cur, out = sys.argv[1], sys.argv[2]
TYPE = sys.argv[4] if len(sys.argv) > 4 else "delivery"
maxp = int(sys.argv[3]) if len(sys.argv) > 3 else 100000
cont = None; allr = []; t0 = time.time()
for i in range(maxp):
    u = f"https://www.deribit.com/api/v2/public/get_last_settlements_by_currency?currency={cur}&type={TYPE}&count=1000" + (f"&continuation={cont}" if cont else "")
    r = get(u)["result"]; s = r["settlements"]; allr += s; cont = r.get("continuation")
    if i % 25 == 0:
        print(i, len(allr), dt.datetime.fromtimestamp(s[-1]["timestamp"] / 1000, dt.timezone.utc) if s else None, f"{time.time()-t0:.0f}s", flush=True)
    if not s or not cont or cont == "none":
        break
json.dump(allr, open(out, "w"))
print("done", len(allr), dt.datetime.fromtimestamp(allr[-1]["timestamp"] / 1000, dt.timezone.utc), f"{time.time()-t0:.0f}s")
