"""s216 — докачка метрик позиций (OI, лонг/шорт; data.binance.vision, часовые строки) на монето-сутки наблюдений s216
и сутки перед ними (для изменений за 24 ч). Кэш — s22/metrics_full (загрузчик s22/h12_fetch.full_day).
Запуск из /home/user/mc_data: python3 <repo>/research/s216/fetch_metrics.py"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s22"))
from h12_fetch import full_day  # noqa: E402


def main():
    D = pd.read_pickle("s21/panel.pkl")
    G = D[D["T"] % (4 * 3600) == 0]
    days = set()
    for s, T in zip(G.s, G["T"]):
        for dt in (0, -86400):
            days.add((s, pd.Timestamp(T + dt, unit="s").strftime("%Y-%m-%d")))
    need = sorted(x for x in days if not os.path.exists(f"s22/metrics_full/{x[0]}/{x[1]}.npy"))
    print("монето-суток", len(days), "докачать", len(need), flush=True)
    t0, done = time.time(), 0
    with ThreadPoolExecutor(8) as ex:
        for _ in ex.map(lambda x: full_day(*x), need):
            done += 1
            if done % 1000 == 0:
                print(f"{done}/{len(need)} за {time.time() - t0:.0f} с", flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
