"""Throughput test: N day-jobs with W threads against history.deribit.com (BTC+ETH options)."""
import sys, random, datetime as dt, subprocess, concurrent.futures as cf, time
W = int(sys.argv[1]); out = sys.argv[2]
random.seed(11)
days = [dt.date(2020, 10, 1) + dt.timedelta(days=random.randrange(2230)) for _ in range(8)]
jobs = [(c, d.isoformat()) for c in ("BTC", "ETH") for d in days]
t0 = time.time()
def run(j):
    r = subprocess.run([sys.executable, "-I", "scripts/drb_day.py", j[0], j[1], out], capture_output=True, text=True)
    return (r.returncode, r.stdout.split(" keys")[0], r.stderr[-200:])
res = list(cf.ThreadPoolExecutor(W).map(run, jobs))
for rc, s, e in res:
    print(rc, s, e.strip()[:120])
print(f"{len(jobs)} jobs, {W} threads: {time.time()-t0:.1f} s")
