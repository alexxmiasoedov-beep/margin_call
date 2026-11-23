"""s259 — проверка: индекс, восстановленный по свече перпа и премии (c / (1 + p)), против настоящего indexPriceKlines архива
Binance (15 мин) на выборке перпов и месяцев. Скачанное — /home/user/mc_data/s259/index_check/ (данные, не код).
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/check_index.py SYM:YYYY-MM …"""
import io
import os
import pickle
import sys
import time
import urllib.parse
import urllib.request
import zipfile

import numpy as np

UA = {"User-Agent": "research-script/1.0"}
DIR = "s259/index_check"


def fetch(sym, m, kind="indexPriceKlines"):
    os.makedirs(DIR, exist_ok=True)
    path = f"{DIR}/{sym}-{kind}-{m}.npy"
    if os.path.exists(path):
        return np.load(path)
    s = urllib.parse.quote(f"{sym}USDT")
    url = f"https://data.binance.vision/data/futures/um/monthly/{kind}/{s}/15m/{s}-15m-{m}.zip"
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines():
                p = ln.split(",")
                if p and p[0].isdigit():
                    rows.append([int(p[0]) // 1000, float(p[1]), float(p[2]), float(p[3]), float(p[4])])
            a = np.array(rows)
            np.save(path, a)
            time.sleep(0.5)
            return a
        except Exception as e:  # noqa: BLE001
            print("сбой", sym, m, e)
            time.sleep(3 * (k + 1))
    return None


def main():
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    PR = pickle.load(open("s12/prem.pkl", "rb"))
    for arg in sys.argv[1:]:
        sym, m = arg.split(":")
        ix = fetch(sym, m)
        if ix is None or not len(ix):
            continue
        a = K[sym]; pt, pv = PR[sym]
        t = ix[:, 0].astype(np.int64)
        ik = np.searchsorted(a["t"], t); ok = (ik < len(a["t"])) & (a["t"][np.minimum(ik, len(a["t"]) - 1)] == t)
        ip = np.searchsorted(pt, t); okp = (ip < len(pt)) & (pt[np.minimum(ip, len(pt) - 1)] == t)
        ok &= okp & (a["qv"][np.minimum(ik, len(a["t"]) - 1)] > 0)
        c = a["c"][ik[ok]].astype(float); p = pv[ip[ok]].astype(float); idx = ix[ok, 4]
        der = c / (1 + p)
        err = der / idx - 1
        last = c / idx - 1                                          # отклонение последней цены от индекса
        r_i = np.diff(np.log(idx)); r_d = np.diff(np.log(der)); r_c = np.diff(np.log(c))
        print(f"{sym} {m}: свечей {ok.sum()}; |восст./индекс − 1|: медиана {np.median(np.abs(err)):.3%}, 95% "
              f"{np.quantile(np.abs(err), .95):.3%}; corr доходностей 15 мин (восст., индекс) {np.corrcoef(r_d, r_i)[0, 1]:.3f}; "
              f"(цена, индекс) {np.corrcoef(r_c, r_i)[0, 1]:.3f}; премия к индексу по последней цене: медиана "
              f"{np.median(last):+.3%}, |…| 90% {np.quantile(np.abs(last), .9):.2%}; премия-индекс p: медиана {np.median(p):+.3%}; "
              f"доля p = 0: {(p == 0).mean():.0%}")


if __name__ == "__main__":
    main()
