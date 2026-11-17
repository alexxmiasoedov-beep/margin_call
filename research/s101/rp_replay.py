"""s101 — почему у ↩️ нет живых сделок с 22.10: настоящая функция бота scanner.repay_rule прогоняется по каждой 15-мин свече
22.10–17.11 на постах канала из веб-версии Telegram (scanner.fetch_posts). Binance не спрашивается: свечи подменены
пустым ответом, поэтому каждое срабатывание правила по отдаче видно строкой «нет фьючерса Binance или свечей за сутки».
Считаются срабатывания до фильтра хода цены. Запуск из корня репозитория: python3 research/s101/rp_replay.py"""
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner  # noqa: E402

T0 = int(datetime(2026, 10, 22, 9, 30, tzinfo=timezone.utc).timestamp())
T1 = int(datetime(2026, 11, 17, 12, 30, tzinfo=timezone.utc).timestamp())
_http = scanner.http


def slow_http(url, *a, **k):
    time.sleep(0.25)                                   # бережно к t.me
    return _http(url, *a, **k)


def main():
    scanner.http = slow_http
    hours = (time.time() - T0) / 3600 + 12
    posts = scanner.fetch_posts(hours, max_pages=900)
    posts.sort(key=lambda p: -p["ts"])
    print(f"постов: {len(posts)}, {datetime.fromtimestamp(posts[-1]['ts'], timezone.utc):%d.%m %H:%M} — "
          f"{datetime.fromtimestamp(posts[0]['ts'], timezone.utc):%d.%m %H:%M} UTC; со строками монет: "
          f"{sum(1 for p in posts if p['rows_all'])}")
    hits = []
    scanner._fut_sym = lambda c: c
    scanner._closed_15m = lambda s, T, n=99: None
    scanner.log = lambda *a, **k: hits.append((NOW[0], " ".join(str(x) for x in a)))
    real_time = time.time
    for T in range(T0, T1, 900):
        NOW[0] = T
        time.time = lambda T=T: T + 60
        ps = [p for p in posts if T - (scanner.LOOKBACK_RP_H + 1) * 3600 <= p["ts"] < T]
        st = {}
        scanner.repay_rule(st, ps)
    time.time = real_time
    hh = [(t, m) for t, m in hits if "нет фьючерса" in m]
    print(f"свечей проверено: {(T1 - T0) // 900}; срабатываний по отдаче (до фильтра хода цены): {len(hh)}")
    for t, m in hh[:30]:
        print(f"  {datetime.fromtimestamp(t, timezone.utc):%d.%m %H:%M} {m}")
    other = [m for _, m in hits if "нет фьючерса" not in m]
    if other:
        print("другие строки:", other[:5])


NOW = [0]

if __name__ == "__main__":
    main()
