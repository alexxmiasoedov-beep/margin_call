"""OI at expiry per Deribit expiry (BTC+ETH inverse options) from public settlement records: notional, type, max pain.
Descriptive only (no returns). Writes data/expiries.json."""
import json, collections, datetime as dt, statistics as stt
U = lambda ts: dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc)
recs = []
for cur in ("BTC", "ETH"):
    a = json.load(open(f"data/drb_settle_{cur}.json"))
    b = [x for x in json.load(open(f"data/drb_all_{cur}_recent.json")) if x["type"] == "exercise"]
    recs += [x for x in a + b if x.get("instrument_name") and x["instrument_name"].count("-") == 3]
E = collections.defaultdict(lambda: {"oi": collections.defaultdict(float), "S": None, "t": None})
for x in recs:
    c, e, k, cp = x["instrument_name"].split("-")
    g = E[(c, e)]; g["oi"][(float(k), cp)] += (x.get("position") or 0.0); g["S"] = x["index_price"]; g["t"] = x["timestamp"]
out = []
for (c, e), g in E.items():
    t = U(g["t"]); S = g["S"]
    notional = sum(v for v in g["oi"].values()) * S
    strikes = sorted(set(k for k, _ in g["oi"]))
    def pay(P):  # total intrinsic paid at settlement price P (in coins * USD)
        return sum(v * (max(P - k, 0) if cp == "C" else max(k - P, 0)) for (k, cp), v in g["oi"].items())
    mp = min(strikes, key=pay) if strikes else None
    last_fri = (t + dt.timedelta(days=7)).month != t.month and t.weekday() == 4
    typ = "Q" if last_fri and t.month in (3, 6, 9, 12) else "M" if last_fri else "W" if t.weekday() == 4 else "D"
    out.append({"cur": c, "exp": e, "t": t.isoformat(), "type": typ, "notional": notional, "S": S, "maxpain": mp,
                "put_call_oi": sum(v for (k, cp), v in g["oi"].items() if cp == "P") / max(1e-9, sum(v for (k, cp), v in g["oi"].items() if cp == "C"))})
json.dump(out, open("data/expiries.json", "w"))
per = [("P1", "2020-10-01", "2022-10-01"), ("P2", "2022-10-01", "2024-10-01"), ("P3", "2024-10-01", "2026-11-01")]
for c in ("BTC", "ETH"):
    for p, a, b in per:
        rows = [r for r in out if r["cur"] == c and a <= r["t"][:10] < b]
        s = {}
        for typ in "QMWD":
            v = [r["notional"] for r in rows if r["type"] == typ]
            s[typ] = f"{len(v)}x med ${stt.median(v)/1e9:.2f}B" if v else "-"
        print(c, p, s)
