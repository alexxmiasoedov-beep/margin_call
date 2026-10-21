"""Данные для моментов после пампов (разворот): стакан, спот, минутки за дни [tp−1 д … tp+1 д] → mm2/raw2/<монета>.pkl."""
import os, pickle, datetime
os.environ["RAWDIR"] = "mm2/raw2"
from concurrent.futures import ProcessPoolExecutor
import collect
UTC = datetime.timezone.utc
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
if __name__ == "__main__":
    K = pickle.load(open("kaia/k15_all.pkl", "rb")); R = pickle.load(open("mm2/rev_moments.pkl", "rb"))
    need = {}
    for r in R:
        t0 = K[r["s"]][r["i"], 0] + 900
        need.setdefault(r["s"], set()).update({day(t0 - 86400), day(t0 - 1)})
    print("монет", len(need), "| монето-дней", sum(len(v) for v in need.values()), flush=True)
    jobs = [(s, sorted(v)) for s, v in sorted(need.items())]
    with ProcessPoolExecutor(3) as ex:
        for n, (s, st) in enumerate(ex.map(collect.load_coin, jobs, chunksize=2)):
            if n % 25 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), "монет", n, s, st, flush=True)
    print("готово", flush=True)
