"""Стоп +100% у 🏦 по марк-цене — как в боте: виртуальный стоп срабатывает, когда максимум марк-цены за минуту достигает
2 × марк-цены входа (trader._virt_scan). Максимум 15-мин свечи марк-цены — максимум её минут, так что проверка та же.
Сравнение: без стопа / стоп по цене сделок (bf_take.py) / стоп по марк-цене; и тейк +5% с хеджем со стопом по марк-цене.

Марк-цена — 15-мин markPriceKlines из открытого архива data.binance.vision: файл на монету и месяц, скачиваются один раз
в папку mark/ (~880 файлов, ~70 МБ). Запуск из папки с данными ветки data: python3 s13/bf_markstop.py"""
import csv
import datetime
import io
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bf_take as bt

UTC = datetime.timezone.utc
CACHE = "mark"
URL = "https://data.binance.vision/data/futures/um/monthly/markPriceKlines/{s}/15m/{s}-15m-{m}.zip"
WEEK = bt.HOLD * bt.BAR


def month(t):
    return datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m")


def have(s, m):
    p = os.path.join(CACHE, f"{s}USDT-15m-{m}")
    return os.path.exists(p + ".zip") or os.path.exists(p + ".none")


def fetch(pair):
    """Месяц марк-цены монеты в mark/: «.zip», или пустой «.none» — в архиве нет. Сбой сети — три попытки с паузой."""
    s, m = pair
    if have(s, m):
        return
    path = os.path.join(CACHE, f"{s}USDT-15m-{m}")
    for i in range(3):
        try:
            with urllib.request.urlopen(URL.format(s=urllib.parse.quote(s + "USDT"), m=m), timeout=60) as r:
                data = r.read()
            with open(path + ".tmp", "wb") as f:
                f.write(data)
            os.replace(path + ".tmp", path + ".zip")
            return
        except urllib.error.HTTPError as e:
            if e.code == 404:
                open(path + ".none", "w").close()
                return
        except OSError:
            pass
        time.sleep(2 * (i + 1))


MK = {}


def load(s):
    """Марк-цена монеты по всем скачанным месяцам: (начало свечи, с; открытие; максимум)."""
    if s not in MK:
        rows = set()
        for fn in sorted(f for f in os.listdir(CACHE) if f.startswith(f"{s}USDT-15m-") and f.endswith(".zip")):
            with zipfile.ZipFile(os.path.join(CACHE, fn)) as z:
                for name in z.namelist():
                    for r in csv.reader(io.TextIOWrapper(z.open(name), "utf-8")):
                        if r and r[0].isdigit():                      # в новых файлах первая строка — заголовок
                            rows.add((int(r[0]) // 1000, float(r[1]), float(r[2])))
        a = np.array(sorted(rows)) if rows else np.zeros((0, 3))
        MK[s] = (a[:, 0].astype(np.int64), a[:, 1], a[:, 2])
    return MK[s]


fallback = set()


def mark(s, t0):
    """Максимумы марк-цены 672 свечей с t0 и марк-цена входа (открытие свечи t0). Если в архиве нет всей недели — стоп по цене
    сделок, сделка попадает в fallback."""
    miss = [m for m in {month(t0), month(t0 + WEEK)} if not have(s, m)]
    if miss:
        for m in miss:
            fetch((s, m))
        MK.pop(s, None)
    t, o, h = load(s)
    j = np.searchsorted(t, t0)
    if j + bt.HOLD <= len(t) and t[j] == t0 and t[j + bt.HOLD - 1] == t0 + WEEK - bt.BAR:
        return h[j:j + bt.HOLD], o[j]
    fallback.add((s, t0))
    a = bt.K[s]; k = np.searchsorted(a["t"], t0)
    return a["h"][k:k + bt.HOLD].astype(float), float(a["o"][k])


def peak(s, t0, src):
    """Максимум за 168 ч к цене входа: по цене сделок или по марк-цене."""
    if src == "mark":
        hi, ref = mark(s, t0)
        return hi.max() / ref
    a = bt.K[s]; k = np.searchsorted(a["t"], t0)
    return a["h"][k:k + bt.HOLD].max() / a["o"][k]


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    need = set()
    for tp, pol, st in ((None, "A", False), (None, "A", True), (0.05, "A", False), (0.05, "B", False)):
        for s, t0 in bt.journal(tp, pol, st)[["s", "T"]].itertuples(index=False):
            need |= {(s, month(t0)), (s, month(t0 + WEEK))}
    todo = sorted(p for p in need if not have(*p))
    t_ = time.time()
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(fetch, todo))
    files = os.listdir(CACHE)
    print(f"марк-цена: нужно {len(need)} месяцев монет, скачано сейчас {len(todo)} за {time.time() - t_:.0f} с; "
          f"в архиве нет {sum(f.endswith('.none') for f in files)}")
    none = bt.journal(None, stop_on=False)
    bt.report("🏦 без стопа", none)
    last = bt.report("🏦 стоп +100% по цене сделок (как в bf_take.py)", bt.journal(None))
    mk = bt.report("🏦 стоп +100% по марк-цене — как в боте", bt.journal(None, mark=mark))
    ref = {(s, t0): h for s, t0, h in none[["s", "T", "h"]].itertuples(index=False)}
    for name, tr in (("по цене сделок", last), ("по марк-цене", mk)):
        st = tr[tr.why == "стоп"]
        kept = [ref[(s, t0)] for s, t0 in zip(st.s, st["T"]) if (s, t0) in ref]
        print(f"\n  стопов {name}: {len(st)}; те же сделки без стопа через 168 ч: в среднем {np.mean(kept) * 100:+.0f}% с хеджем, "
              f"хуже −100% — {sum(k < -1 for k in kept)} из {len(kept)}")
    print("\n  сделки, где цена сделок за 168 ч хоть раз была ≥ ×2 (вход — дата UTC):")
    for s, t0 in zip(none.s, none["T"]):
        pl = peak(s, t0, "last")
        if pl >= 2:
            pm = peak(s, t0, "mark")
            print(f"    {s:10s} {datetime.datetime.fromtimestamp(t0, UTC):%d.%m.%Y}: максимум цены сделок ×{pl:.2f}, марк-цены ×{pm:.2f}"
                  f" → стоп по марк-цене {'да' if pm >= 2 else 'нет'}; без стопа через 168 ч {ref[(s, t0)] * 100:+.0f}% с хеджем")
    for pol, txt in (("A", "снова шорт на ближайшем наборе"), ("B", "ждать конца 168 ч")):
        bt.report(f"тейк +5% с хеджем ({pol} — {txt}), стоп по марк-цене", bt.journal(0.05, pol, mark=mark))
    for x in (3.0, 4.0):                                             # стоп выше — нужна маржа больше суммы шорта
        bt.STOP_X = x
        bt.report(f"🏦 стоп +{(x - 1) * 100:.0f}% по марк-цене (при ×1 изолированной маржи биржа ликвидирует около +100%)",
                  bt.journal(None, mark=mark))
    bt.STOP_X = 2.0
    pk = [peak(s, t, "last") for s, t in sorted(fallback)]
    print(f"\nсделок без полной недели марк-цены в архиве (стоп по цене сделок): {len(fallback)}"
          + (f"; максимум цены сделок у них до ×{max(pk):.2f}" if pk else ""))
    print("    " + ", ".join(f"{s} {datetime.datetime.fromtimestamp(t, UTC):%d.%m.%y}" for s, t in sorted(fallback)))
