"""s263 — метрики позиций (OI, доля счетов в лонге, топ-трейдеры, отношение покупок к продажам тейкеров) из архива
data.binance.vision (daily/metrics, шаг 5 мин) для самых торгуемых TradFi-перпов. ~3 запроса в секунду.

Запуск из /home/user/mc_data: python3 -I <путь>/fetch_metrics.py [N=30] [с даты 2026-07-01]
Выход: /dev/shm/s263/metrics.pkl — символ → DataFrame(t, oi, oi_usd, top_acc_ls, top_pos_ls, acc_ls, taker_ls)."""
import csv
import datetime
import io
import os
import pickle
import sys
import time
import urllib.error
import urllib.request
import zipfile

import pandas as pd

SHM = "/dev/shm/s263"
UA = {"User-Agent": "research-script/1.0"}
UTC = datetime.timezone.utc
_last = [0.0]


def get(url):
    for i in range(5):
        w = _last[0] + 0.34 - time.time()
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return None


def num(x):
    try:
        return float(x)
    except ValueError:
        return float("nan")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    d0 = datetime.date.fromisoformat(sys.argv[2] if len(sys.argv) > 2 else "2026-07-01")
    d1 = datetime.date(2026, 11, 22)
    vol = pd.read_csv("s263/desc_volume_sym.csv").sort_values("qv30", ascending=False)
    meta = pd.read_csv("s263/tf_meta.csv").set_index("sym")
    syms = list(vol.sym[:n])
    for extra in ("XAU", "XAG", "CL", "SPY", "QQQ", "SOXS", "SKHYNIX", "SAMSUNG", "TSLA", "SNDK"):
        if extra not in syms:
            syms.append(extra)
    out_p = f"{SHM}/metrics.pkl"
    out = pickle.load(open(out_p, "rb")) if os.path.exists(out_p) else {}
    t0 = time.time()
    for j, s in enumerate(syms):
        if s in out:
            continue
        on = datetime.datetime.fromtimestamp(int(meta.loc[s, "onboard"]), UTC).date()
        d = max(d0, on)
        rows = []
        while d <= d1:
            url = f"https://data.binance.vision/data/futures/um/daily/metrics/{s}USDT/{s}USDT-metrics-{d.isoformat()}.zip"
            raw = get(url)
            if raw:
                z = zipfile.ZipFile(io.BytesIO(raw))
                for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
                    if not r or not r[0][:1].isdigit():
                        continue
                    t = int(datetime.datetime.fromisoformat(r[0]).replace(tzinfo=UTC).timestamp())
                    rows.append((t, num(r[2]), num(r[3]), num(r[4]), num(r[5]), num(r[6]), num(r[7])))
            d += datetime.timedelta(1)
        out[s] = pd.DataFrame(rows, columns=["t", "oi", "oi_usd", "top_acc_ls", "top_pos_ls", "acc_ls", "taker_ls"])
        pickle.dump(out, open(out_p, "wb"), protocol=4)
        print(f"{j + 1}/{len(syms)} {s}: строк {len(rows)}; {time.time() - t0:.0f} с", flush=True)
    print("готово", len(out))


if __name__ == "__main__":
    main()
