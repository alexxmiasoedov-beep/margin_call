"""s228 — часовые метрики позиций всех дней для вселенной s228 (метод — ВЫВОДЫ.md, записан до расчёта).

Вселенная — монеты с папкой в s22/metrics_full, без стейблкоинов и BL_SKIP. Дни — от первой до последней свечи с оборотом
(s224/k_d.pkl) в пределах 01.10.2024 – 19.11.2026. Готовые сутки берутся из s22/metrics_full и s224/work/s22/metrics_full,
остальные скачиваются с data.binance.vision тем же разбором, что s22/h12_fetch.full_day (строки HH:00:00, столбцы:
время, OI, OI $, лонг/шорт топ-счетов, топ-позиций, всех счетов, отношение агрессивных объёмов).
Итог по монете — s228/met/<фьючерс>.npz: t (int64, с), v (float32, 6 столбцов). Сбой сети — монета не пишется, повтор
при следующем запуске. Запуск из /home/user/mc_data: MC_K=s224/k_d.pkl python3 <repo>/research/s228/fetch.py"""
import datetime
import io
import os
import pickle
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
UTC = datetime.timezone.utc
DAY = 86400
D0, D1 = datetime.date(2024, 10, 1), datetime.date(2026, 11, 19)
SRC = ("s22/metrics_full", "s224/work/s22/metrics_full")
OUT = "s228/met"
UA = {"User-Agent": "research-script/1.0"}


def universe():
    os.environ.setdefault("STATE_FILE", os.path.join(tempfile.mkdtemp(), "state.json"))
    sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
    import scanner  # noqa: E402
    skip = set(scanner.BL_SKIP) | set(scanner.C4_STABLE)
    return sorted(s for s in os.listdir("s22/metrics_full") if s not in skip)


def parse(raw):
    rows = []
    for ln in raw.decode().splitlines()[1:]:
        p = ln.split(",")
        if len(p) >= 8 and p[0].endswith(":00:00"):
            t = datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
            rows.append([t] + [float(x) if x else np.nan for x in p[2:8]])
    return np.array(rows) if rows else np.zeros((0, 7))


def get_day(sym, day):
    """Сутки метрик: массив (n, 7); пустой — файла нет (404); None — сбой сети."""
    url = f"https://data.binance.vision/data/futures/um/daily/metrics/{sym}USDT/{sym}USDT-metrics-{day}.zip"
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            return parse(z.read(z.namelist()[0]))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return np.zeros((0, 7))
            time.sleep(2 + 3 * k)
        except Exception:
            time.sleep(2 + 3 * k)
    return None


def main():
    K = pickle.load(open(os.environ.get("MC_K", "s224/k_d.pkl"), "rb"))
    os.makedirs(OUT, exist_ok=True)
    syms = [s for s in universe() if s in K]
    print("монет во вселенной", len(syms), flush=True)
    t0 = time.time(); dl = 0
    with ThreadPoolExecutor(24) as ex:
        for n, s in enumerate(syms):
            out = f"{OUT}/{s}.npz"
            if os.path.exists(out):
                continue
            nz = np.flatnonzero(K[s]["qv"] > 0)
            if not len(nz):
                continue
            lo = datetime.datetime.fromtimestamp(float(K[s]["t"][nz[0]]), UTC).date()
            hi = datetime.datetime.fromtimestamp(float(K[s]["t"][nz[-1]]), UTC).date()
            days = [lo + datetime.timedelta(d) for d in range((hi - lo).days + 1)]
            days = [d.isoformat() for d in days if D0 <= d <= D1]
            have, need = {}, []
            for d in days:
                for src in SRC:
                    p = f"{src}/{s}/{d}.npy"
                    if os.path.exists(p):
                        have[d] = np.load(p); break
                else:
                    need.append(d)
            got = list(ex.map(lambda d: get_day(s, d), need))
            dl += len(need)
            if any(g is None for g in got):
                print(f"{s}: сбой сети на {sum(g is None for g in got)} сутках — повтор при следующем запуске", flush=True)
                continue
            arr = [a for a in list(have.values()) + got if len(a)]
            A = np.vstack(arr) if arr else np.zeros((0, 7))
            A = A[np.argsort(A[:, 0], kind="stable")]
            if len(A):
                keep = np.r_[True, np.diff(A[:, 0]) > 0]
                A = A[keep]
            np.savez(out, t=A[:, 0].astype(np.int64), v=A[:, 1:].astype(np.float32))
            if n % 10 == 0:
                print(f"{n + 1}/{len(syms)} {s}: суток {len(days)}, было {len(have)}, скачано {len(need)}; "
                      f"всего скачано {dl} за {time.time() - t0:.0f} с", flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
