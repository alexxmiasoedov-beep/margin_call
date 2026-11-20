"""s245 — признаки «глубокого стакана» из bookDepth data.binance.vision (метод — ВЫВОДЫ.md, записан до выгрузки).
Период P1 (01.01.2023–30.09.2024, свечи s117/k_oos.pkl) или P2 (01.10.2024–19.10.2026, s2/k2y.pkl): 100 фьючерсов
с наибольшим медианным суточным оборотом, дни сигнала — каждые третьи сутки с 01.01.2023. Для дня сигнала d берётся файл
дня d − 1 и средние заявки ($) до ±1…±5% за 23:00–24:00 UTC. Файлы не хранятся: признаки — s245/feat_<P>.pkl.
Запуск из /home/user/mc_data: python3 <repo>/research/s245/fetch.py P1|P2 [потоков]"""
import io
import json
import os
import pickle
import sys
import threading
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd

PER = {"P1": ("s117/k_oos.pkl", "2023-01-01", "2024-09-30"), "P2": ("s2/k2y.pkl", "2024-10-01", "2026-10-19")}
SKIP = {"BTC", "ETH", "USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD", "USDE",
        "XAU", "XAG", "PAXG", "XAUT"}
UA = {"User-Agent": "research-script/1.0"}
URL = "https://data.binance.vision/data/futures/um/daily/bookDepth/{s}USDT/{s}USDT-bookDepth-{d}.zip"


def universe(kp, d0, d1):
    """100 криптофьючерсов по медианному суточному обороту: без BTC, ETH, стейблкоинов, индексов и токенизированных акций
    и сырья (underlyingType ≠ COIN или TRADIFI_PERPETUAL в exchangeInfo, s245/noncrypto.json)."""
    non = set(json.load(open("s245/noncrypto.json")))
    K = pickle.load(open(kp, "rb"))
    t0, t1 = pd.Timestamp(d0, tz="UTC").timestamp(), pd.Timestamp(d1, tz="UTC").timestamp() + 86400
    med = {}
    for s, a in K.items():
        if s in SKIP or s in non or not isinstance(a, dict) or "qv" not in a:
            continue
        t = a["t"].astype(np.int64); m = (t >= t0) & (t < t1)
        if m.sum() < 96 * 60:
            continue
        day = pd.Series(a["qv"][m].astype(float)).groupby(t[m] // 86400).sum()
        day = day[day > 0]
        if len(day) >= 60:
            med[s] = float(day.median())
    return [s for s, _ in sorted(med.items(), key=lambda x: -x[1])[:100]]


def feat(raw, day):
    """Средние заявки ($) по уровням −5…−1 и 1…5 за 23:00–24:00 UTC дня day; None — нет снимков."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        txt = z.read(z.namelist()[0]).decode()
    i = txt.find(f"{day} 23:")
    if i < 0:
        return None
    acc, n = {}, {}
    for ln in txt[i:].splitlines():
        p = ln.split(",")
        if len(p) < 4:
            continue
        try:
            k = int(float(p[1])); v = float(p[3])
        except ValueError:
            continue
        acc[k] = acc.get(k, 0.0) + v; n[k] = n.get(k, 0) + 1
    if not all(k in acc for k in (-5, -1, 1, 5)):
        return None
    out = {f"{'b' if k < 0 else 'a'}{abs(k)}": acc[k] / n[k] for k in acc if k in (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)}
    out["snaps"] = n[1]
    return out


def main():
    P = sys.argv[1]; nthr = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    kp, d0, d1 = PER[P]
    U = universe(kp, d0, d1)
    json.dump(U, open(f"s245/universe_{P}.json", "w"))
    print(P, "монет:", len(U), U[:12], flush=True)
    days = [d for d in pd.date_range("2023-01-01", "2026-10-19", freq="3D") if pd.Timestamp(d0) <= d <= pd.Timestamp(d1)]
    jobs = [(s, d) for d in days for s in U]
    out_p = f"s245/feat_{P}.pkl"
    os.makedirs("s245", exist_ok=True)
    rows = pd.read_pickle(out_p).to_dict("records") if os.path.exists(out_p) else []
    done = {(r["s"], r["d"]) for r in rows} | set()
    miss_p = f"s245/miss_{P}.txt"
    miss = set(open(miss_p).read().split("\n")) if os.path.exists(miss_p) else set()
    jobs = [(s, d) for s, d in jobs if (s, d.strftime("%Y-%m-%d")) not in done and f"{s} {d:%Y-%m-%d}" not in miss]
    print("дней", len(days), "заданий", len(jobs), flush=True)
    lock = threading.Lock(); t0 = time.time(); cnt = [0]

    def work():
        while True:
            with lock:
                if not jobs:
                    return
                s, d = jobs.pop()
            prev = (d - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            raw = None
            for k in range(4):
                try:
                    with urllib.request.urlopen(urllib.request.Request(URL.format(s=s, d=prev), headers=UA), timeout=60) as r:
                        raw = r.read(); break
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        break
                    time.sleep(2 * (k + 1))
                except Exception:
                    time.sleep(2 * (k + 1))
            f = feat(raw, prev) if raw else None
            with lock:
                cnt[0] += 1
                if f:
                    f.update(s=s, d=d.strftime("%Y-%m-%d")); rows.append(f)
                else:
                    miss.add(f"{s} {d:%Y-%m-%d}")
                if cnt[0] % 2000 == 0:
                    pd.DataFrame(rows).to_pickle(out_p); open(miss_p, "w").write("\n".join(sorted(miss)))
                    print(f"{cnt[0]} файлов, признаков {len(rows)}, нет {len(miss)}, {(time.time() - t0) / 60:.1f} мин", flush=True)

    th = [threading.Thread(target=work) for _ in range(nthr)]
    for x in th:
        x.start()
    for x in th:
        x.join()
    pd.DataFrame(rows).to_pickle(out_p); open(miss_p, "w").write("\n".join(sorted(miss)))
    print(P, "готово: признаков", len(rows), "нет файлов", len(miss), flush=True)


if __name__ == "__main__":
    main()
