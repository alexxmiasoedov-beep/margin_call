"""s91 — мера «человеческой» доли пампа по сделкам фьючерса: aggTrades из data.binance.vision за день пампа (и за прошлый
день, если окно его задевает), окно 2 ч до закрытия свечи пампа. Тейкерские покупки до 5000 $; круглая — количество
1/2/2,5/5 × 10^k монет или сумма в пределах 0,1% от 1/2/2,5/5 × 10^k USDT (от 10 $). Только пампы основной группы
(без входов 🇰🇷 и 🛒 за сутки, 🔝 и 👀 за 7 сут). Файлы не сохраняются — разбираются в памяти.
Результат — s91/human.pkl {(фьючерс, индекс свечи пампа): dict(n, vol, share, share_n, share_q, share_u) | None}:
None — файла нет. Прерванный сбор продолжается. Запуск из папки с данными: python3 <путь>/s91/human_fetch.py"""
import datetime
import io
import os
import pickle
import time
import urllib.error
import urllib.request
import zipfile
from multiprocessing import Pool

import numpy as np
import pandas as pd

OUT = "s91/human.pkl"
WIN = 2 * 3600
URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/{s}USDT/{s}USDT-aggTrades-{d}.zip"
DAY = 86400
ROUND = (1.0, 2.0, 2.5, 5.0, 10.0)


def overlap_sets():
    S65 = pd.read_pickle("s65/trades.pkl"); S83 = pd.read_pickle("s83/trades.pkl")
    S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    wk, dy = {}, {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S83.s, S83.t)):
        wk.setdefault(s, []).append(t)
    for s, t in list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        dy.setdefault(s, []).append(t)
    return {s: np.array(v) for s, v in wk.items()}, {s: np.array(v) for s, v in dy.items()}


def fetch(s, d):
    """Сделки дня: DataFrame, None — файла нет (404), "ERR" — сбой сети."""
    for i in range(4):
        try:
            b = urllib.request.urlopen(urllib.request.Request(URL.format(s=s, d=d), headers={"User-Agent": "margin-call research"}),
                                       timeout=90).read()
            z = zipfile.ZipFile(io.BytesIO(b)); n = z.namelist()[0]
            hdr = 0 if z.open(n).readline()[:1].isdigit() else 1
            parts = []                                           # кусками: в памяти — только сделки окна (WIN_MS)
            for ch in pd.read_csv(z.open(n), header=None, skiprows=hdr, usecols=[1, 2, 5, 6], names=["p", "q", "t", "m"],
                                  chunksize=400_000):
                t = ch.t.values
                if len(t) and t.max() > 1e14:
                    t = t // 1000
                keep = (t > WIN_MS[0]) & (t <= WIN_MS[1])
                if keep.any():
                    parts.append(ch[keep].assign(t=t[keep]))
            return pd.concat(parts) if parts else pd.DataFrame(columns=["p", "q", "t", "m"])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
        time.sleep(3 * (i + 1))
    return "ERR"


def rnd(x, tol):
    """Круглое ли число: мантисса 1, 2, 2,5, 5 (или 10) с относительной погрешностью tol."""
    m = x / 10.0 ** np.floor(np.log10(x))
    r = np.zeros(len(x), bool)
    for v in ROUND:
        r |= np.abs(m - v) <= tol * v
    return r


WIN_MS = [0, 0]


def measure(job):
    s, j, tc = job
    t0 = tc - WIN
    WIN_MS[0], WIN_MS[1] = t0 * 1000, tc * 1000
    days = sorted({datetime.datetime.fromtimestamp(x, datetime.timezone.utc).strftime("%Y-%m-%d") for x in (t0 + 1, tc)})
    parts = []
    for d in days:
        x = fetch(s, d)
        if isinstance(x, str):
            return (s, j), "ERR"
        if x is not None:
            parts.append(x)
    if not parts:
        return (s, j), None
    a = pd.concat(parts)
    t = a.t.values.astype(np.int64)
    if len(t) and t.max() > 1e14:                                # микросекунды
        t = t // 1000
    mk = a.m.astype(str).str.lower().eq("true").values           # is_buyer_maker: True — тейкер продаёт
    p, q = a.p.values.astype(float), a.q.values.astype(float)
    u = p * q
    sel = (t > t0 * 1000) & (t <= tc * 1000) & ~mk & (u <= 5000) & (q > 0)
    p, q, u = p[sel], q[sel], u[sel]
    n = int(sel.sum())
    if n == 0:
        return (s, j), dict(n=0, vol=0.0, share=np.nan, share_n=np.nan, share_q=np.nan, share_u=np.nan)
    rq = rnd(q, 1e-6)
    ru = (u >= 9.99) & rnd(u, 1e-3)
    r = rq | ru
    vol = float(u.sum())
    return (s, j), dict(n=n, vol=vol, share=float(u[r].sum() / vol), share_n=float(r.mean()),
                        share_q=float(u[rq].sum() / vol), share_u=float(u[ru].sum() / vol))


def all_jobs():
    """Пампы основной группы (фьючерс, индекс свечи, закрытие свечи) — один раз в s91/jobs.pkl, чтобы процессы разбора
    не держали в памяти архив 15-мин свечей."""
    if os.path.exists("s91/jobs.pkl"):
        return pickle.load(open("s91/jobs.pkl", "rb"))
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    wk, dy = overlap_sets()
    jobs = []
    for s, js in PU.items():
        w, d = wk.get(s, np.zeros(0)), dy.get(s, np.zeros(0))
        for j in js:
            tc = int(K[s]["t"][j]) + 900
            if ((w <= tc) & (w >= tc - 7 * DAY)).any() or ((d <= tc) & (d >= tc - DAY)).any():
                continue
            jobs.append((s, int(j), tc))
    pickle.dump(jobs, open("s91/jobs.pkl", "wb"))
    return jobs


def main():
    if "--jobs" in os.sys.argv:                                  # только составить список пампов и выйти
        print(f"пампов основной группы: {len(all_jobs())}")
        return
    res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
    jobs = [x for x in all_jobs() if not ((x[0], x[1]) in res and res[(x[0], x[1])] != "ERR")]
    print(f"пампов основной группы к разбору: {len(jobs)}", flush=True)
    done = 0
    with Pool(6) as pool:
        for key, v in pool.imap_unordered(measure, jobs, chunksize=4):
            res[key] = v; done += 1
            if done % 200 == 0:
                pickle.dump(res, open(OUT + ".tmp", "wb")); os.replace(OUT + ".tmp", OUT)
                print(f"  {done}/{len(jobs)}", flush=True)
    pickle.dump(res, open(OUT + ".tmp", "wb")); os.replace(OUT + ".tmp", OUT)
    print(f"готово: {len(res)}, сбоев {sum(1 for v in res.values() if v == 'ERR')}, без файла "
          f"{sum(1 for v in res.values() if v is None)}", flush=True)


if __name__ == "__main__":
    main()
