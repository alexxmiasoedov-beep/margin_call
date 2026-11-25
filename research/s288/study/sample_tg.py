"""s288: выборочные страницы канала t.me/s/<канал>?before=<id> (для описи малого канала whale_alert).
Запуск: python3 -I sample_tg.py <канал> <папка сырья> <id через запятую>; не чаще 1 запроса в 1,1 с."""
import gzip
import os
import sys
import time
import urllib.request

chan, out, ids = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
os.makedirs(out, exist_ok=True)
for b in ids:
    url = f"https://t.me/s/{chan}" + (f"?before={b}" if b else "")
    for k in range(4):
        try:
            body = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-script/1.0"}),
                                          timeout=40).read()
            with gzip.open(os.path.join(out, f"p_{b}.html.gz"), "wb") as f:
                f.write(body)
            break
        except Exception as e:  # noqa: BLE001
            print("сбой", b, type(e).__name__, flush=True)
            time.sleep(5 * (k + 1))
    time.sleep(1.1)
print("готово", len(ids), flush=True)
