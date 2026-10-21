"""Догрузка постов канала после 16.10 → posts_oct2.jsonl."""
exec(open("scrape.py").read().split("seen = set()")[0])
from concurrent.futures import ThreadPoolExecutor
last = page(); top = max(p[0] for p in last); print("последний пост", top, max(last)[1], flush=True)
res = {p[0]: p for p in last}
with ThreadPoolExecutor(10) as ex:
    for pp in ex.map(page, range(172800, top + 21, 20)):
        for p in pp: res[p[0]] = p
with open("posts_oct2.jsonl", "w") as f:
    for k in sorted(res): f.write(json.dumps(res[k], ensure_ascii=False) + "\n")
ids = sorted(res); print("готово", len(res), ids[0], ids[-1], res[ids[-1]][1], "пропусков id:", sum(1 for a, b in zip(ids, ids[1:]) if b - a > 1), flush=True)
