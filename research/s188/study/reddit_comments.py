"""s188 — текст и лучшие комментарии отобранных тредов Reddit через архив Arctic Shift (posts/ids, comments/tree).
Отбор — по рейтингу из reddit_read.py (top.json), до 4 тредов на тему, плюс id из аргументов. Пауза 4 с, при отказе
архива 60–180 с. Итог — /home/user/mc_data/s188/reddit/threads.json и печать выдержек в лог (без имён авторов)."""
import json
import sys
import time
import urllib.parse
import urllib.request

R = "/home/user/mc_data/s188/reddit"
UA = {"User-Agent": "research-script/1.0"}
B = "https://arctic-shift.photon-reddit.com/api"
PER_TOPIC = int(sys.argv[1]) if len(sys.argv) > 1 else 4
EXTRA = sys.argv[2].split(",") if len(sys.argv) > 2 else []


def get(path, **q):
    url = f"{B}/{path}?" + urllib.parse.urlencode(q)
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                x = json.loads(r.read().decode())
            time.sleep(4)
            if isinstance(x, dict) and x.get("error"):
                raise RuntimeError(x["error"])
            return x
        except Exception as e:
            print("  архив/сеть:", path, e, flush=True)
            time.sleep(60 * (i + 1))
    return None


def walk(node, out):
    """Собрать комментарии (body, score) из дерева любого вида."""
    if isinstance(node, list):
        for z in node:
            walk(z, out)
    elif isinstance(node, dict):
        d = node.get("data") if isinstance(node.get("data"), dict) else node
        if "body" in d:
            out.append((d.get("score") or 0, d.get("body") or ""))
        for k in ("replies", "children", "data"):
            v = d.get(k) if isinstance(d, dict) else None
            if isinstance(v, (list, dict)) and v is not d:
                walk(v, out)


top = json.load(open(f"{R}/top.json"))
ids = []
for k, rows in top.items():
    for r in rows[:PER_TOPIC]:
        if r["num_comments"] >= 5 and r["id"] not in ids:
            ids.append(r["id"])
ids += [i for i in EXTRA if i and i not in ids]
print("тредов:", len(ids), flush=True)
posts = {}
for i in range(0, len(ids), 50):
    x = get("posts/ids", ids=",".join(ids[i:i + 50]), fields="id,title,selftext,score,num_comments,created_utc,subreddit")
    for p in (x or {}).get("data") or []:
        posts[p["id"]] = p
out = {}
for pid in ids:
    p = posts.get(pid, {"id": pid})
    x = get("comments/tree", link_id=f"t3_{pid}", limit=300)
    cm = []
    walk((x or {}).get("data") or [], cm)
    cm.sort(key=lambda z: -z[0])
    out[pid] = dict(post=p, comments=cm[:12])
    t = time.strftime('%Y-%m-%d', time.gmtime(p.get("created_utc", 0)))
    print(f"\n### r/{p.get('subreddit')} {t} ↑{p.get('score')} комм. {p.get('num_comments')}: {p.get('title', '')}",
          flush=True)
    st = (p.get("selftext") or "").replace("\n", " ")
    if st:
        print("  ТЕКСТ:", st[:900])
    for s, b in cm[:8]:
        print(f"  [{s}] {b.replace(chr(10), ' ')[:450]}")
json.dump(out, open(f"{R}/threads.json", "w"), ensure_ascii=False)
