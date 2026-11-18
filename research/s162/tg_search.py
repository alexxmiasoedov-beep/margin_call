"""s162 — посты канала по поиску t.me/s/<канал>?q=<слово>&before=<id> (без аккаунта): только посты со словом.
Кэш — s137/tg_<канал>_q_<слово>.json в папке данных: [[id, время, текст]]; прерванная выгрузка продолжается.
Запуск из /home/user/mc_data: python3 <repo>/research/s162/tg_search.py <канал> <слово> [<слово> …]"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "research-script/1.0"}


def page(ch, q, before=None):
    url = f"https://t.me/s/{ch}?q={urllib.parse.quote(q)}" + (f"&before={before}" if before else "")
    for i in range(6):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8", "replace")
        except Exception:
            time.sleep(5 * (i + 1))
    return None


def parse(h):
    out = []
    for block in h.split('class="tgme_widget_message_wrap')[1:]:
        m = re.search(r'data-post="[^/]+/(\d+)"', block); t = re.search(r'<time datetime="([^"]+)"', block)
        x = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
        if m and t:
            txt = html.unescape(re.sub(r"<[^>]+>", " ", x.group(1))) if x else ""
            out.append([int(m.group(1)), t.group(1), re.sub(r"\s+", " ", txt).strip()])
    return out


def crawl(ch, q):
    path = f"s137/tg_{ch}_q_{q}.json"
    posts = {p[0]: p for p in json.load(open(path))} if os.path.exists(path) else {}
    before = min(posts) if posts else None
    n = 0
    while True:
        h = page(ch, q, before)
        if h is None:
            print(ch, q, "сеть не отвечает, остановка", flush=True); break
        got = parse(h)
        new = [p for p in got if p[0] not in posts]
        for p in got:
            posts[p[0]] = p
        if not new:
            break
        before = min(p[0] for p in got); n += 1
        if n % 20 == 0:
            json.dump(sorted(posts.values()), open(path, "w"), ensure_ascii=False)
            print(ch, q, "страниц", n, "постов", len(posts), "самый старый", posts[min(posts)][1][:10], flush=True)
        time.sleep(1.5)
    json.dump(sorted(posts.values()), open(path, "w"), ensure_ascii=False)
    print("готово", ch, q, len(posts), posts[min(posts)][1][:10] if posts else "", flush=True)


if __name__ == "__main__":
    for q in sys.argv[2:]:
        crawl(sys.argv[1], q)
