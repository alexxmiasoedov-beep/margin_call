"""Download all Deribit option trades for one currency and one UTC day via history.deribit.com.
Usage: python3 -I drb_day.py CUR YYYY-MM-DD OUTDIR  -> OUTDIR/CUR_YYYY-MM-DD.jsonl.gz, prints stats."""
import sys, json, gzip, time, datetime as dt, urllib.request, os
UA = {"User-Agent": "research-script/1.0"}
def get(url, tries=6):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:
            time.sleep(1.5 * (k + 1))
    raise RuntimeError(url)
cur, day, out = sys.argv[1], sys.argv[2], sys.argv[3]
kind = sys.argv[4] if len(sys.argv) > 4 else "option"
d0 = dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)
st = int(d0.timestamp() * 1000); en = st + 86400_000
t0 = time.time(); nreq = 0; rows = []; seen = set()
cursor = st
while True:
    u = (f"https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time?currency={cur}&kind={kind}"
         f"&start_timestamp={cursor}&end_timestamp={en}&count=1000&sorting=asc")
    r = get(u)["result"]; nreq += 1
    tr = r["trades"]
    new = [x for x in tr if x["trade_id"] not in seen]
    for x in new:
        seen.add(x["trade_id"]); rows.append(x)
    if not r.get("has_more") or not tr:
        break
    last = tr[-1]["timestamp"]
    cursor = last if new else last + 1
os.makedirs(out, exist_ok=True)
with gzip.open(f"{out}/{cur}_{kind}_{day}.jsonl.gz", "wt") as f:
    for x in rows:
        f.write(json.dumps(x) + "\n")
vol = sum(x["amount"] for x in rows)
blk = sum(1 for x in rows if x.get("block_trade_id"))
liq = sum(1 for x in rows if x.get("liquidation"))
print(f"{cur} {kind} {day}: trades={len(rows)} req={nreq} sec={time.time()-t0:.1f} amount={vol:.0f} block={blk} liq={liq} keys={sorted(set(k for x in rows[:2000] for k in x))}")
