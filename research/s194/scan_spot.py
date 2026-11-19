"""s194 — потоковый прогон лент aggTrades спота Binance для Г1 «продавец запаса на споте» (ВЫВОДЫ.md, записано
до расчёта). Задания — все монето-сутки ликвидной вселенной s193/s183 периода с оборотом спота в панели s183 (sqv > 0).
Пара — монета без множителя + USDT, если файла нет — имя перпа + USDT. Признаки — только обнаруженные прогоны D1/D1n
(`s193/study/tape.py` как есть) и итоги суток; zip удаляется сразу после разбора.

Запуск: python3 scan_spot.py <период> [число процессов]  → /home/user/mc_data/s194/parts/<период>_NNNN.pkl.gz
Докачка: уже посчитанные задания пропускаются. User-Agent «research-script/1.0»; сбой сети — пауза 5 / 20 / 60 с."""
import gzip
import os
import pickle
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from multiprocessing import Pool

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s193", "study"))
import tape  # noqa: E402

D = "/home/user/mc_data/s194"
TMP = f"{D}/tmp"
PARTS = f"{D}/parts"
UA = {"User-Agent": "research-script/1.0"}
DAY = 86400


def base(perp):
    return re.sub(r"^(1000000|100000|10000|1000|100|1M)(?=[A-Z0-9])", "", perp)


def url(sym, d):
    day = pd.Timestamp(d, unit="s").strftime("%Y-%m-%d")
    return f"https://data.binance.vision/data/spot/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"


def fetch(u, path):
    for pause in (5, 20, 60, None):
        try:
            req = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            return 200
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return e.code
            err = e.code
        except Exception as e:  # noqa: BLE001
            err = str(e)[:80]
        if pause is None:
            return f"err {err}"
        time.sleep(pause)
    return "err"


def jobs(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s193", "study"))
    import jobs as J  # noqa: E402
    U = J.universe()[per]
    P = pd.read_pickle(f"/home/user/mc_data/s183/daily_{per}.pkl")[["s", "d", "sqv"]]
    x = U[(U.qv7 >= 5e6) & (U.age >= 30)].merge(P, on=["s", "d"], how="left")
    x = x[x.sqv.fillna(0) > 0]
    return [dict(s=s, d=int(d), per=per) for s, d in zip(x.s, x.d)]


def lean(path, sym, day):
    df = tape.read_zip(path)
    if len(df) < 200:
        return dict(ok=0, code="мало сделок", n_agg=len(df))
    day0 = int(day) * 1000
    df = df[(df["T"] >= day0) & (df["T"] < day0 + tape.DAYMS)]
    if len(df) < 200:
        return dict(ok=0, code="мало сделок", n_agg=len(df))
    O, p, t, side, q = tape.orders(df)
    ctx = tape.Ctx(O)
    rq, _ = tape.d1_exact(O, ctx, day0)
    rn, _ = tape.d1_notional(O, ctx, day0)
    runs = [r for r in rq + rn if np.isfinite(r["det_t"])]
    return dict(ok=1, n_agg=len(df), n_ord=len(O["t"]), vol=float(O["v"].sum()),
                volb=float(O["v"][O["s"] > 0].sum()), p_open=float(p[0]), p_close=float(p[-1]), runs=runs)


def work(job):
    s, d = job["s"], job["d"]
    key = (s, d)
    path = f"{TMP}/{os.getpid()}_{s}_{d}.zip"
    t0 = time.time()
    tried = []
    code = None
    for sym in dict.fromkeys([base(s) + "USDT", s + "USDT"]):
        tried.append(sym)
        code = fetch(url(sym, d), path)
        if code not in (403, 404):          # файл есть или сбой сети — запасное имя не пробуем
            break
    t1 = time.time()
    if code != 200:
        return dict(key=key, per=job["per"], ok=0, code=code, sym=tried[-1])
    try:
        r = lean(path, sym, d)
        r.update(key=key, per=job["per"], s=s, d=d, sym=sym, t_dl=t1 - t0, t_cpu=time.time() - t1,
                 mb=os.path.getsize(path) / 1e6)
        return r
    except Exception:  # noqa: BLE001
        return dict(key=key, per=job["per"], ok=0, code="exc " + traceback.format_exc()[-300:], sym=sym)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def done_keys(per):
    out = set()
    for f in sorted(os.listdir(PARTS)):
        if f.startswith(per) and f.endswith(".pkl.gz"):
            with gzip.open(f"{PARTS}/{f}", "rb") as g:
                for r in pickle.load(g):
                    out.add(r["key"])
    return out


def main():
    per = sys.argv[1]
    nproc = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(PARTS, exist_ok=True)
    for f in os.listdir(TMP):
        os.remove(f"{TMP}/{f}")
    J = jobs(per)
    have = done_keys(per)
    J = [j for j in J if (j["s"], j["d"]) not in have]
    rng = np.random.default_rng(194)
    J = [J[i] for i in rng.permutation(len(J))]
    if lim:
        J = J[:lim]
    print(f"{per}: к обработке {len(J)} заданий (уже есть {len(have)})", flush=True)
    k = len([f for f in os.listdir(PARTS) if f.startswith(per) and f.endswith(".pkl.gz")])
    buf, n, t0, mb, bad = [], 0, time.time(), 0.0, 0
    with Pool(nproc) as pool:
        for r in pool.imap_unordered(work, J, chunksize=4):
            buf.append(r)
            n += 1
            mb += r.get("mb", 0.0)
            bad += int(not r.get("ok"))
            if len(buf) >= 1000:
                with gzip.open(f"{PARTS}/{per}_{k:04d}.pkl.gz", "wb", compresslevel=3) as g:
                    pickle.dump(buf, g, protocol=5)
                k += 1
                buf = []
            if n % 1000 == 0:
                el = time.time() - t0
                print(f"{n}/{len(J)} {el / 60:.1f} мин, {mb / 1024:.1f} ГБ, без файла/ошибка {bad}, "
                      f"осталось ~{el / n * (len(J) - n) / 60:.0f} мин", flush=True)
    if buf:
        with gzip.open(f"{PARTS}/{per}_{k:04d}.pkl.gz", "wb", compresslevel=3) as g:
            pickle.dump(buf, g, protocol=5)
    print(f"готово: {n} заданий, {mb / 1024:.1f} ГБ, {(time.time() - t0) / 60:.1f} мин", flush=True)


if __name__ == "__main__":
    main()
