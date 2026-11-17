"""s72 — посты канала BinanceLiquidations (ликвидации Binance USDT-M от ~50 тыс. $: монета, сторона, сумма, цена) с t.me/s,
без аккаунта Telegram. Номера постов идут подряд, страницы «before=N» качаются в 4 потока шагом 20. Итог — s72/liq.jsonl:
[номер, время ISO, текст]; пишется по ходу, при перезапуске уже скачанные страницы пропускаются.
Запуск из папки с данными: python3 <repo>/research/s72/liq_scrape.py"""
import datetime
import html
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CH = "BinanceLiquidations"
SINCE = datetime.datetime(2024, 9, 20, tzinfo=datetime.timezone.utc)
OUT = "s72/liq.jsonl"


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
    os.makedirs("s72", exist_ok=True)
    have = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            have.add(json.loads(line)[0])
    first = page()
    hi = max(p[0] for p in first) + 1
    lo, top = 1, hi
    while top - lo > 40:                                       # номер поста на SINCE — двоичным поиском
        mid = (lo + top) // 2
        d = date_of(mid)
        if d is None or d < SINCE:
            lo = mid
        else:
            top = mid
    befores = [b for b in range(hi, lo - 20, -20) if not all(n in have for n in range(b - 20, b) if n >= lo)]
    print(f"номера постов: {lo} … {hi}, уже есть {len(have)}, страниц качать {len(befores)}", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex, open(OUT, "a") as f:
        for k, pp in enumerate(ex.map(page, befores)):
            for p in pp:
                if p[0] not in have:
                    have.add(p[0]); f.write(json.dumps(p, ensure_ascii=False) + "\n")
            if k % 250 == 0:
                f.flush()
                print(f"  страниц {k}/{len(befores)}, постов {len(have)}, {time.time() - t0:.0f} с", flush=True)
    print("готово:", len(have), "постов", flush=True)
