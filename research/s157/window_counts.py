"""Frequency only (no returns): how many journal-like entries fall into option-calendar windows, per period."""
import pickle, json, datetime as dt, numpy as np, pandas as pd
E = json.load(open("data/expiries.json"))
btc = [e for e in E if e["cur"] == "BTC"]
tq = np.array(sorted(dt.datetime.fromisoformat(e["t"]).timestamp() for e in btc if e["type"] in "QM"))
tw = np.array(sorted(dt.datetime.fromisoformat(e["t"]).timestamp() for e in btc if e["type"] in "QMW"))
per = {"P1": (dt.datetime(2020, 10, 1), dt.datetime(2022, 10, 1)), "P2": (dt.datetime(2022, 10, 1), dt.datetime(2024, 10, 1)),
       "P3": (dt.datetime(2024, 10, 1), dt.datetime(2026, 11, 1))}
def ts(d): return d.replace(tzinfo=dt.timezone.utc).timestamp()
def inwin(t, ex, before, after):
    i = np.searchsorted(ex, t)          # next expiry >= t
    nxt = ex[np.minimum(i, len(ex) - 1)]; prv = ex[np.maximum(i - 1, 0)]
    return ((nxt - t >= 0) & (nxt - t < before * 3600)) | ((t - prv >= 0) & (t - prv < after * 3600))
OWN = {"BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "HYPE", "AVAX", "TRX", "MNT"}
sets = {}
p = pd.read_pickle("/home/user/mc_data/s132_pumps.pkl")
for k in per:
    a, b = per[k]; sets[("pumps(s132)", k)] = (p[(p.t >= ts(a)) & (p.t < ts(b))].t.values, p[(p.t >= ts(a)) & (p.t < ts(b))].s.values)
for k, f in (("P1", "2020–2022"), ("P2", "2022–2024"), ("P3", "2024–2026")):
    u = pd.read_pickle(f"/home/user/mc_data/s142_{f}.pkl"); sets[("unlocks(s142)", k)] = (u.t.values.astype(float), u.s.values)
    g = pd.read_pickle(f"/home/user/mc_data/s147_{f}.pkl"); g = g[g.r <= -0.01]
    sets[("fund<=-1%(s147)", k)] = (g.t.values.astype(float), g.s.values)
print(f"{'set':18s} per    N  N/mon  M/Q-24h  M/Q+48h  weekly-24h  ownOpt")
for (name, k), (t, s) in sets.items():
    a, b = per[k]; months = (b - a).days / 30.44
    n = len(t)
    w1 = inwin(t, tq, 24, 0).mean() if n else 0
    w2 = inwin(t, tq, 0, 48).mean() if n else 0
    w3 = inwin(t, tw, 24, 0).mean() if n else 0
    own = np.isin(s, list(OWN)).mean() if n else 0
    print(f"{name:18s} {k}  {n:5d} {n/months:6.1f}  {w1:7.1%}  {w2:7.1%}  {w3:9.1%}  {own:6.1%}")
print("time share: M/Q-24h", f"{24*12/8766:.1%}", "M/Q+48h", f"{48*12/8766:.1%}", "weekly-24h", f"{24*52/8766:.1%}")
