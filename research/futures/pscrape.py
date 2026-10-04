exec(open("scrape.py").read().split("seen = set()")[0])
from concurrent.futures import ThreadPoolExecutor
res = {}; done = 0
def job(b):
    return page(b)
with ThreadPoolExecutor(12) as ex:
    for pp in ex.map(job, range(110000, 169420, 20)):
        for p in pp: res[p[0]] = p
        done += 1
        if done % 200 == 0: print(done, len(res), flush=True)
with open("posts.jsonl", "w") as f:
    for k in sorted(res): f.write(json.dumps(res[k], ensure_ascii=False) + "\n")
ids = sorted(res); print("готово", len(res), "пропусков id:", sum(1 for a, b in zip(ids, ids[1:]) if b - a > 20))
