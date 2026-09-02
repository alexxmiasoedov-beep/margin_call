import re, html, json, time, subprocess, sys, datetime

OUT = sys.argv[2] if len(sys.argv) > 2 else "posts.jsonl"
CUTOFF = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=int(sys.argv[1]) if len(sys.argv) > 1 else 7)

def fetch(before=None):
    url = "https://t.me/s/cryptocode_margin_data" + (f"?before={before}" if before else "")
    for i in range(5):
        r = subprocess.run(["curl", "-sS", "-m", "30", url], capture_output=True, text=True)
        if r.returncode == 0 and "tgme_widget_message" in r.stdout:
            return r.stdout
        time.sleep(2 * (i + 1))
    raise RuntimeError("fetch failed " + url)

def parse(page):
    out = []
    blocks = re.split(r'(?=<div class="tgme_widget_message_wrap)', page)
    for b in blocks:
        m = re.search(r'data-post="cryptocode_margin_data/(\d+)"', b)
        if not m:
            continue
        pid = int(m.group(1))
        t = re.search(r'<time datetime="([^"]+)"', b)
        txt = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
        raw = html.unescape(re.sub(r'<[^>]+>', '', re.sub(r'<br\s*/?>', '\n', txt.group(1)))) if txt else ""
        out.append({"id": pid, "ts": t.group(1) if t else None, "text": raw})
    return out

seen = set()
rows = []
before = None
while True:
    page = fetch(before)
    posts = parse(page)
    if not posts:
        break
    new = [p for p in posts if p["id"] not in seen]
    for p in new:
        seen.add(p["id"])
    rows.extend(new)
    oldest = min(posts, key=lambda p: p["id"])
    ots = datetime.datetime.fromisoformat(oldest["ts"])
    print(f"page before={before}: {len(new)} new, oldest {oldest['id']} {ots}", flush=True)
    if ots < CUTOFF or not new:
        break
    before = oldest["id"]
    time.sleep(0.7)

rows.sort(key=lambda p: p["id"])
with open(OUT, "w") as f:
    for p in rows:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")
print("saved", len(rows))
