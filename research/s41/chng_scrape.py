"""s41 — посты канала cryptocode_margin_data с колонкой CHNG (с 02.09.2025) с t.me/s: номера постов идут подряд, поэтому
страницы «before=N» качаются в 4 потока шагом 20. Итог — s41/posts.jsonl: [номер, время ISO, текст]. Запуск из папки с данными."""
import datetime
import html
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CH = "cryptocode_margin_data"
SINCE = datetime.datetime(2025, 9, 1, tzinfo=datetime.timezone.utc)


def get(u):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                x = r.read().decode("utf-8", "replace")
                if "tgme_widget_message" in x:
                    return x
        except Exception:
            pass
        time.sleep(2 + 3 * i)
    return ""


def page(before=None):
    p = get(f"https://t.me/s/{CH}" + (f"?before={before}" if before else ""))
    out = []
    for b in re.split(r'(?=<div class="tgme_widget_message_wrap)', p):
        m = re.search(rf'data-post="{CH}/(\d+)"', b); t = re.search(r'<time datetime="([^"]+)"', b)
        x = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
        if m and t:
            out.append((int(m.group(1)), t.group(1),
                        html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", x.group(1)))) if x else ""))
    return out


def date_of(n):
    pp = page(n)
    return datetime.datetime.fromisoformat(min(pp)[1]) if pp else None


if __name__ == "__main__":
    first = page()
    hi = max(p[0] for p in first) + 1
    lo, top = 1, hi
    while top - lo > 40:                                       # номер поста на 01.09.2025 — двоичным поиском
        mid = (lo + top) // 2
        d = date_of(mid)
        if d is None or d < SINCE:
            lo = mid
        else:
            top = mid
    print(f"номера постов: {lo} … {hi}, страниц {(hi - lo) // 20 + 1}", flush=True)
    seen = {}
    befores = list(range(hi, lo - 20, -20))
    with ThreadPoolExecutor(4) as ex:
        for k, pp in enumerate(ex.map(page, befores)):
            for p in pp:
                seen[p[0]] = p
            if k % 500 == 0:
                print(f"  страниц {k}/{len(befores)}, постов {len(seen)}", flush=True)
    with open("s41/posts.jsonl", "w") as f:
        for n in sorted(seen):
            f.write(json.dumps(seen[n], ensure_ascii=False) + "\n")
    print("готово:", len(seen), "постов")
