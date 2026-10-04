"""Посты канала cryptocode_margin_data с 14.03.2026 → posts.jsonl (id, время, текст)."""
import re, html, json, time, subprocess, datetime, os
SINCE = datetime.datetime(2026, 3, 13, tzinfo=datetime.timezone.utc)
def curl(u):
    for i in range(5):
        r = subprocess.run(["curl", "-sS", "-m", "30", u], capture_output=True, text=True)
        if r.stdout and "tgme_widget_message" in r.stdout: return r.stdout
        time.sleep(2 + i * 2)
    return ""
def page(before=None):
    p = curl("https://t.me/s/cryptocode_margin_data" + (f"?before={before}" if before else ""))
    out = []
    for b in re.split(r'(?=<div class="tgme_widget_message_wrap)', p):
        m = re.search(r'data-post="cryptocode_margin_data/(\d+)"', b); t = re.search(r'<time datetime="([^"]+)"', b)
        x = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
        if m and t: out.append((int(m.group(1)), t.group(1), html.unescape(re.sub(r'<[^>]+>', '', re.sub(r'<br\s*/?>', '\n', x.group(1)))) if x else ""))
    return out
seen = set(); before = None; f = open("posts.jsonl", "w"); n = 0
while True:
    pp = page(before)
    if not pp: print("пустая страница на", before, flush=True); break
    for p in pp:
        if p[0] not in seen: seen.add(p[0]); f.write(json.dumps(p, ensure_ascii=False) + "\n")
    o = min(pp); before = o[0]; n += 1
    if n % 50 == 0: print(n, o[1], flush=True); f.flush()
    if datetime.datetime.fromisoformat(o[1]) < SINCE: break
f.close(); print("готово", len(seen))
