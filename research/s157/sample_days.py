"""Sample random days of Deribit option trades to estimate total download volume. Usage: python3 -I sample_days.py OUTDIR"""
import sys, random, datetime as dt, subprocess, concurrent.futures as cf
out = sys.argv[1]
random.seed(7)
days = []
d0 = dt.date(2020, 10, 1); d1 = dt.date(2026, 11, 15)
span = (d1 - d0).days
for k in range(12):
    days.append(d0 + dt.timedelta(days=int(span * (k + random.random()) / 12)))
jobs = [(c, d.isoformat()) for c in ("BTC", "ETH") for d in days]
def run(j):
    c, d = j
    r = subprocess.run([sys.executable, "-I", "scripts/drb_day.py", c, d, out], capture_output=True, text=True)
    return r.stdout.strip()[:110]
with cf.ThreadPoolExecutor(4) as ex:
    for s in ex.map(run, jobs):
        print(s, flush=True)
