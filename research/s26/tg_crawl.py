"""Публичный Telegram-канал через веб-превью t.me/s/<канал>?before=<id> (без аккаунта): посты от новых к старым до даты.
Кэш — s26/tg_<канал>.json: [[id, время UTC ISO, текст]]. Пауза между страницами 1 с. Запуск из папки с данными:
python3 tg_crawl.py <канал> <ГГГГ-ММ-ДД> [начать до id] — третий аргумент, чтобы перескочить пачку повторов
(у bithumb_notice 03.05.2026 — посты 3090…25277)."""
import html
import json
import os
import re
import sys
import time
import urllib.request

ch, since = sys.argv[1], sys.argv[2]
path = f"s26/tg_{ch}.json"
posts = {int(p[0]): p for p in json.load(open(path))} if os.path.exists(path) else {}
MSG = re.compile(r'data-post="[^/]+/(\d+)".*?<time datetime="([^"]+)"', re.S)


def page(before=None):
    url = f"https://t.me/s/{ch}" + (f"?before={before}" if before else "")
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; margin_call)"})
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        except Exception:
            time.sleep(3 + 3 * i)
    return ""


def parse(h):
    out = []
    for block in h.split('class="tgme_widget_message_wrap')[1:]:
        m = re.search(r'data-post="[^/]+/(\d+)"', block)
        t = re.search(r'<time datetime="([^"]+)"', block)
        x = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
        if not (m and t):
            continue
        txt = html.unescape(re.sub(r"<[^>]+>", " ", x.group(1))) if x else ""
        out.append([int(m.group(1)), t.group(1), re.sub(r"\s+", " ", txt).strip()])
    return out


before = int(sys.argv[3]) if len(sys.argv) > 3 else None; n = 0
while True:
    got = parse(page(before))
    if not got:
        break
    for p in got:
        posts[p[0]] = p
    oldest = min(p[0] for p in got)
    n += 1
    if n % 20 == 0:
        print(f"  страниц {n}, постов {len(posts)}, самый старый {min(posts.values(), key=lambda p: p[0])[1][:10]}", flush=True)
        json.dump(sorted(posts.values()), open(path, "w"), ensure_ascii=False)
    if min(p[1] for p in got) < since or oldest <= 1:
        break
    before = oldest
    time.sleep(1)
json.dump(sorted(posts.values()), open(path, "w"), ensure_ascii=False)
print(f"готово: {ch}, постов {len(posts)}, с {min(p[1] for p in posts.values())[:10]} по {max(p[1] for p in posts.values())[:10]}")
