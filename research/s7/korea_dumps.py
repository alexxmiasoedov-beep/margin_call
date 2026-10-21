"""Upbit и Bithumb: 15-мин свечи вокруг каждого дампа (−24 ч … +26 ч от входа) → mm2/korea2y/ (тот же формат, что у пампов)."""
import pickle, re, datetime, sys
src = open("/home/user/margin_call/research/mm2/korea2y.py").read().split("jobs = []")[0]
exec(src)
EV = pickle.load(open("s7/dumps.pkl", "rb"))
MK = {ex: {x["market"][4:] for x in get(f"{b}/v1/market/all") or [] if x["market"].startswith("KRW-")} for ex, (b, tz) in EXS.items()}
print("KRW-рынков:", {ex: len(v) for ex, v in MK.items()}, flush=True)
jobs = [(ex, strip(e["s"]), e["t_in"] + 26 * 3600) for e in EV for ex in EXS if strip(e["s"]) in MK[ex]]
print("запросов", len(jobs), flush=True)
fails = 0
with ThreadPoolExecutor(8) as pool:
    for n, f in enumerate(pool.map(job, jobs)):
        fails += f
        if n % 1000 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), n, "сбоев", fails, flush=True)
print("готово, сбоев", fails, flush=True)
