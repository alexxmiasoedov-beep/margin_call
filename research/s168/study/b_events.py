"""s167 area B, step 1: approximate s160 'large transfer to exchange' events from the raw collection (read-only use of
/home/user/mc_data/s160). Same filters as s160/events.py: recipient = exchange address that is not custody/prime broker,
sender not exchange and not the zero address, amount >= 0.5% of CMC circulating supply at the (approximate) date.
Output: work/b_events.json (one row per transfer) for label coverage."""
import glob, gzip, json, re, sys, bisect
import numpy as np
D = "/home/user/mc_data/s160"
OUT = sys.argv[1]
S = json.load(open(f"{D}/sets.json")); CEX = S["cex"]; TOK = S["toks"]
CUST = re.compile(r"prime|anchorage|falconx|bitcoin suisse|copper|bitgo|fireblocks|cumberland|galaxy|wintermute|amber|matrixport|"
                  r"ceffu|hex trust|komainu|cobo|paxos|custody", re.I)
lab = {a: " ".join(v) for a, v in CEX.items()}
cust = {a for a in CEX if CUST.search(lab[a])}
bt = {int(k): v for k, v in json.load(open(f"{D}/cache_blocktime.json")).items()}
B = np.array(sorted(bt)); T = np.array([bt[b] for b in B], float)
ids = json.load(open(f"{D}/cmc_ids.json"))
circ = {}
for tok, v in ids.items():
    try:
        rows = [(d, c) for d, c, _ in json.load(open(f"{D}/circ/{v['id']}.json")) if c]
    except Exception:
        continue
    if rows:
        circ[tok] = ([r[0] for r in rows], [r[1] for r in rows])
import datetime as dt
ev = []; n_all = 0
for p in sorted(glob.glob(f"{D}/raw/b*.json.gz")):
    for blk, tok, frm, to, amt, tx, li in json.load(gzip.open(p, "rt")):
        n_all += 1
        if to not in CEX or to in cust or frm in CEX or frm == "0x" + "0" * 40:
            continue
        c = circ.get(tok)
        if not c:
            continue
        t = float(np.interp(blk, B, T))
        d = dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
        k = bisect.bisect_right(c[0], d) - 1
        if k < 0 or c[1][k] <= 0:
            continue
        fr = amt / c[1][k]
        if fr >= 0.005:
            ev.append(dict(block=blk, t=int(t), date=d, tok=tok, sym=TOK[tok]["sym"], frm=frm, to=to, exch=CEX[to][0], frac=fr, tx=tx))
json.dump(ev, open(OUT, "w"))
print("raw rows", n_all, "events >=0.5%", len(ev), "distinct senders", len({e['frm'] for e in ev}), "tokens", len({e['tok'] for e in ev}))
