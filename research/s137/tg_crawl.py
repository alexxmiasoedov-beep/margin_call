"""s137 — выгрузка публичных Telegram-каналов торговых сигналов через веб-превью t.me/s/<канал>?before=<id> (без аккаунта).
Посты от новых к старым до первого. Кэш — s137/tg_<канал>.json в папке данных: [[id, время UTC ISO, текст]], переносы строк
сохранены как «\n». Пауза между страницами 1 с, при сбое — 5, 10, 15 с, потом минута (до 20 раз). Прерванная выгрузка
продолжается с самого старого поста в кэше. Диапазон «<канал>:<до id>:<по id>» качается в отдельный кэш
s137/tg_<канал>__<до id>.json — так один канал выгружается несколькими процессами. Запуск из папки с данными:
python3 <repo>/research/s137/tg_crawl.py <канал>[:<до id>:<по id>] […]"""
import html
import json
import os
import re
import sys
import time
import urllib.request

UA = {"User-Agent": "research-script/1.0"}


def page(ch, before=None):
    url = f"https://t.me/s/{ch}" + (f"?before={before}" if before else "")
    for i in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
        except Exception:
            time.sleep(5 * (i + 1))
    return None


def parse(h):
    out = []
    for block in h.split('class="tgme_widget_message_wrap')[1:]:
        m = re.search(r'data-post="[^/]+/(\d+)"', block)
        t = re.search(r'<time datetime="([^"]+)"', block)
        x = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
        if not (m and t):
            continue
        txt = ""
        if x:
            txt = re.sub(r"<br\s*/?>", "\n", x.group(1))
            txt = html.unescape(re.sub(r"<[^>]+>", "", txt))
            txt = "\n".join(re.sub(r"[ \t ]+", " ", ln).strip() for ln in txt.split("\n")).strip()
        out.append([int(m.group(1)), t.group(1), txt])
    return out


def crawl(spec):
    ch, b0, stop = (spec.split(":") + ["", ""])[:3]
    b0 = int(b0) if b0 else None
    stop = int(stop) if stop else 1
    path = f"s137/tg_{ch}.json" if b0 is None else f"s137/tg_{ch}__{b0}.json"
    posts = {int(p[0]): p for p in json.load(open(path))} if os.path.exists(path) else {}
    before = min(posts) if posts else b0
    n, fails = 0, 0
    while True:
        h = page(ch, before)
        if h is None:                                           # сбой сети — не конец канала
            fails += 1
            if fails > 20:
                print(f"{spec}: сеть не отвечает, остановка на id {before}", flush=True)
                break
            time.sleep(60)
            continue
        fails = 0
        got = parse(h)
        if not got:                                             # пустой ответ под нагрузкой или разрыв из удалённых постов
            for k, back in enumerate((0, 0, 0, 20, 100, 300, 1000, 3000)):
                if before is not None and before - back <= 1:
                    break
                time.sleep(20 if k < 3 else 2)
                h = page(ch, before - back if before else None)
                got = parse(h) if h else []
                if got:
                    break
            if not got:
                break
        for p in got:
            posts[p[0]] = p
        oldest = min(p[0] for p in got)
        n += 1
        if n % 50 == 0:
            print(f"{spec}: страниц {n}, постов {len(posts)}, самый старый {posts[min(posts)][1][:10]}", flush=True)
            json.dump(sorted(posts.values()), open(path, "w"), ensure_ascii=False)
        if oldest <= stop or (before is not None and oldest >= before):
            break
        before = oldest
        time.sleep(1)
    json.dump(sorted(posts.values()), open(path, "w"), ensure_ascii=False)
    if posts:
        print(f"готово: {spec}, постов {len(posts)}, с {posts[min(posts)][1][:10]} по {posts[max(posts)][1][:10]}", flush=True)


if __name__ == "__main__":
    os.makedirs("s137", exist_ok=True)
    for c in sys.argv[1:]:
        crawl(c)
