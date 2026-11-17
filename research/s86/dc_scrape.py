"""s86 — заголовки и время постов «биткоин-галереи» DCInside (gall.dcinside.com, id bitcoins_new1) с 01.10.2024 по 19.10.2026
(время сайта — KST). Список по 100 постов на страницу, страницы — от новых к старым в 3 потока с паузами; повторы (новые
посты сдвигают страницы) убираются по номеру поста. Итог — s86/dc.jsonl: [номер, время KST, заголовок]; скачанные
страницы — s86/pages.txt (при перезапуске пропускаются). Запуск из папки с данными: python3 <repo>/research/s86/dc_scrape.py"""
import html
import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "https://gall.dcinside.com/board/lists/?id=bitcoins_new1&list_num=100&page={}"
START, END = "2024-10-01 00:00:00", "2026-10-19 23:59:59"          # KST
OUT, DONE = "s86/dc.jsonl", "s86/pages.txt"
ROW = re.compile(r'<tr class="ub-content[^"]*" data-no="(\d+)" data-type="([^"]*)"(.*?)</tr>', re.S)
TIT = re.compile(r'<td class="gall_tit[^"]*">.*?<a[^>]*>(.*?)</a>', re.S)
DAT = re.compile(r'<td class="gall_date" title="([^"]+)"')
lock = threading.Lock()


def get(page):
    for k in range(6):
        try:
            req = urllib.request.Request(URL.format(page), headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            time.sleep(30 * (k + 1) if e.code in (403, 429, 503) else 3 * (k + 1))
        except Exception:
            time.sleep(3 * (k + 1))
    return None


def parse(s):
    out = []
    for no, typ, body in ROW.findall(s or ""):
        if "notice" in typ or "ad" == typ:
            continue
        t, d = TIT.search(body), DAT.search(body)
        if t and d:
            title = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t.group(1))).split())
            out.append((int(no), d.group(1), title))
    return out


def first_date(page):
    rows = parse(get(page))
    return max(rows)[1] if rows else None                           # самый свежий пост страницы


def find(date):
    """Наименьшая страница, на которой самый свежий пост не новее date."""
    lo, hi = 1, 40000
    while hi - lo > 1:
        mid = (lo + hi) // 2
        d = first_date(mid)
        if d is None or d <= date:
            hi = mid
        else:
            lo = mid
        time.sleep(1)
    return hi


def main():
    os.makedirs("s86", exist_ok=True)
    done = set(int(x) for x in open(DONE)) if os.path.exists(DONE) else set()
    p0 = max(1, find(END) - 2); p1 = find(START) + 2
    print(f"страницы {p0} … {p1}, уже скачано {len(done)}", flush=True)
    todo = [p for p in range(p0, p1 + 1) if p not in done]
    t0 = time.time(); n = [0]

    def job(p):
        time.sleep(random.uniform(0.2, 0.8))
        rows = parse(get(p))
        if not rows:
            return
        with lock:
            with open(OUT, "a") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            with open(DONE, "a") as f:
                f.write(f"{p}\n")
            n[0] += 1
            if n[0] % 500 == 0:
                print(f"  страниц {n[0]}/{len(todo)}, последняя дата {rows[-1][1]}, {time.time() - t0:.0f} с", flush=True)

    with ThreadPoolExecutor(3) as ex:
        list(ex.map(job, todo))
    print("готово", flush=True)


if __name__ == "__main__":
    main()
