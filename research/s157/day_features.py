"""Sanity check: daily option features from one day of Deribit trades (no returns).
25-delta risk reversal (7-45 d), ATM IV, taker net buying by type. Usage: python3 -I day_features.py FILE..."""
import sys, gzip, json, math, datetime as dt, statistics as st
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
def expiry(code):  # e.g. 27DEC24 -> 08:00 UTC
    d, m, y = int(code[:-5]), MON[code[-5:-2]], 2000 + int(code[-2:])
    return dt.datetime(y, m, d, 8, tzinfo=dt.timezone.utc).timestamp()
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
for f in sys.argv[1:]:
    rows = [json.loads(l) for l in gzip.open(f, "rt")]
    calls, puts, atm = [], [], []
    flow = {"C": [0.0, 0.0], "P": [0.0, 0.0]}  # taker buy, taker sell (USD notional)
    for x in rows:
        _, e, k, cp = x["instrument_name"].split("-")
        T = (expiry(e) - x["timestamp"] / 1000) / (365 * 86400)
        S = x["index_price"]; K = float(k); iv = x.get("iv")
        usd = x["amount"] * S
        flow[cp][0 if x["direction"] == "buy" else 1] += usd
        if not iv or T <= 0 or x.get("block_trade_id") or x.get("combo_id"):
            continue
        s = iv / 100
        d1 = (math.log(S / K) + 0.5 * s * s * T) / (s * math.sqrt(T))
        delta = ncdf(d1) if cp == "C" else ncdf(d1) - 1
        if 7 / 365 <= T <= 45 / 365:
            if cp == "C" and 0.2 <= delta <= 0.3: calls.append(iv)
            if cp == "P" and -0.3 <= delta <= -0.2: puts.append(iv)
            if 0.45 <= abs(delta) <= 0.55: atm.append(iv)
    rr = st.median(calls) - st.median(puts) if calls and puts else float("nan")
    nb = lambda c: (flow[c][0] - flow[c][1]) / 1e6
    print(f"{f.split('/')[-1][:24]}: RR25(7-45d)={rr:+.1f} vol pts (n={len(calls)}/{len(puts)}), ATM IV={st.median(atm) if atm else float('nan'):.1f}, "
          f"taker net buy calls ${nb('C'):+.0f}M puts ${nb('P'):+.0f}M, put share of volume {(sum(flow['P']))/(sum(flow['P'])+sum(flow['C'])):.2f}")
