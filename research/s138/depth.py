"""s138 — глубина стакана фьючерсов Binance перед пампами (bookDepth, data.binance.vision, с 01.01.2023). Для каждого пампа
(s, t; t — закрытие свечи пампа) — медианы накопленного объёма заявок в $: покупатели и продавцы в 1% и 2% от середины
за [t − 8 ч, t − 2 ч) (до пампа) и продавцы и покупатели в 2% за [t − 30 мин, t), число снимков. Пампы — ~/mc_oos/s118_spot.pkl
(с 01.01.2023) и s49/trades.pkl. Сырые файлы не хранятся; результат дописывается в s138/depth.pkl в папке данных после
каждой монеты, прерванная загрузка продолжается. Запуск из /home/user/mc_data: python3 <repo>/research/s138/depth.py"""
import concurrent.futures as cf
import csv
import datetime
import io
import os
import time
import urllib.error
import urllib.request
import zipfile

import numpy as np
import pandas as pd

URL = "https://data.binance.vision/data/futures/um/daily/bookDepth/{s}USDT/{s}USDT-bookDepth-{d}.zip"
UA = {"User-Agent": "research-script/1.0"}
OUT = "s138/depth.pkl"
T0, H = 1672531200, 3600                                       # 01.01.2023


def pumps():
    a = pd.read_pickle("/home/user/mc_oos/s118_spot.pkl")[["s", "t"]]
    a = a[a.t >= T0 + 8 * H]
    b = pd.read_pickle("s49/trades.pkl")[["s", "t"]]
    return pd.concat([a, b]).drop_duplicates().sort_values(["s", "t"]).reset_index(drop=True)


def day(s, d):
    """Снимки за сутки d: индекс — время (с), столбцы — уровни −2, −1, 1, 2 (%), значения — объём в $; None — файла нет."""
    raw = None
    for i in range(4):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(URL.format(s=s, d=d), headers=UA), timeout=60).read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    if raw is None:
        return None
    z = zipfile.ZipFile(io.BytesIO(raw))
    ts, lv, nv = [], [], []
    with z.open(z.namelist()[0]) as f:
        for r in csv.reader(io.TextIOWrapper(f)):
            if len(r) < 4 or r[0] == "timestamp":
                continue
            p = float(r[1])
            if p in (-2.0, -1.0, 1.0, 2.0):
                ts.append(r[0]); lv.append(p); nv.append(float(r[3]))
    if not ts:
        return None
    t = (pd.to_datetime(pd.Series(ts), utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)
    X = pd.DataFrame({"ts": t.values, "p": lv, "n": nv})
    return X.pivot_table(index="ts", columns="p", values="n", aggfunc="last")


def dates(t):
    a = datetime.datetime.fromtimestamp(t - 8 * H, datetime.UTC).date()
    b = datetime.datetime.fromtimestamp(t - 1, datetime.UTC).date()
    return {str(a), str(b)}


def med(x, c):
    return float(x[c].median()) if c in x.columns and len(x) else np.nan


def stats(W, t):
    pre = W[(W.index >= t - 8 * H) & (W.index < t - 2 * H)]
    late = W[(W.index >= t - 1800) & (W.index < t)]
    return dict(B2=med(pre, -2.0), A2=med(pre, 2.0), B1=med(pre, -1.0), A1=med(pre, 1.0), npre=len(pre),
                A2late=med(late, 2.0), B2late=med(late, -2.0), nlate=len(late))


def main():
    os.makedirs("s138", exist_ok=True)
    P = pumps()
    done = pd.read_pickle(OUT) if os.path.exists(OUT) else pd.DataFrame(columns=["s", "t"])
    have = set(zip(done.s, done.t))
    rows = done.to_dict("records")
    todo = P[[(s, t) not in have for s, t in zip(P.s, P.t)]]
    print("пампов", len(P), "осталось", len(todo), flush=True)
    with cf.ThreadPoolExecutor(8) as ex:
        for k, (s, g) in enumerate(todo.groupby("s")):
            need = sorted(set().union(*[dates(t) for t in g.t]))
            frames = [W for W in ex.map(lambda d: day(s, d), need) if W is not None]
            W = pd.concat(frames).sort_index() if frames else pd.DataFrame()
            for t in g.t:
                rows.append(dict(s=s, t=int(t), **(stats(W, int(t)) if len(W) else dict(npre=0, nlate=0))))
            if k % 20 == 0:
                pd.DataFrame(rows).to_pickle(OUT)
                print(f"монет {k}, пампов {len(rows)}", flush=True)
    pd.DataFrame(rows).to_pickle(OUT)
    print("готово, пампов", len(rows), flush=True)


if __name__ == "__main__":
    main()
