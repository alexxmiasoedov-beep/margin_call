"""Загрузка архива Binance USDT-M (data.binance.vision) с кэшем: свечи, марк-свечи, фандинг."""
import os, io, zipfile, subprocess, time, csv, threading
import numpy as np
CACHE = "cache"; os.makedirs(CACHE, exist_ok=True)
BASE = "https://data.binance.vision/data/futures/um"
def fetch(path):
    fn = os.path.join(CACHE, path.replace("/", "_"))
    if os.path.exists(fn): return open(fn, "rb").read() or None
    tmp = f"{fn}.{threading.get_ident()}.tmp"
    for i in range(4):
        r = subprocess.run(["curl", "-sS", "-m", "60", "-w", "%{http_code}", "-o", tmp, f"{BASE}/{path}"], capture_output=True, text=True)
        if r.stdout == "404":
            open(fn, "wb").close()
            if os.path.exists(tmp): os.remove(tmp)
            return None
        if r.stdout == "200": os.replace(tmp, fn); return open(fn, "rb").read()
        time.sleep(2 + 2 * i)
    return None
def rows(data):
    if not data: return []
    try: z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile: return []
    out = []
    for ln in z.read(z.namelist()[0]).decode().splitlines():
        p = ln.split(",")
        if p and p[0][:1].isdigit(): out.append(p)
    return out
def klines(sym, kind, interval, monthly=(), daily=()):
    """kind: klines | markPriceKlines. Возвращает массив [t_сек, o, h, l, c]."""
    out = []
    for m in monthly: out += rows(fetch(f"monthly/{kind}/{sym}USDT/{interval}/{sym}USDT-{interval}-{m}.zip"))
    for d in daily: out += rows(fetch(f"daily/{kind}/{sym}USDT/{interval}/{sym}USDT-{interval}-{d}.zip"))
    if not out: return None
    a = np.array([[int(p[0]) // 1000, float(p[1]), float(p[2]), float(p[3]), float(p[4])] for p in out])
    a = a[np.argsort(a[:, 0])]; _, u = np.unique(a[:, 0], return_index=True)
    return a[u]
def funding(sym, months):
    out = []
    for m in months:
        for p in rows(fetch(f"monthly/fundingRate/{sym}USDT/{sym}USDT-fundingRate-{m}.zip")):
            out.append((int(p[0]) // 1000, float(p[2])))
    return np.array(sorted(out)) if out else None


def kfull(sym, kind, interval, monthly=(), daily=()):
    """Все колонки свечей: t, o, h, l, c, volume, quote_volume, trades, taker_buy_quote."""
    out = []
    for m in monthly: out += rows(fetch(f"monthly/{kind}/{sym}USDT/{interval}/{sym}USDT-{interval}-{m}.zip"))
    for d in daily: out += rows(fetch(f"daily/{kind}/{sym}USDT/{interval}/{sym}USDT-{interval}-{d}.zip"))
    if not out: return None
    a = np.array([[int(p[0]) // 1000] + [float(p[i]) for i in (1, 2, 3, 4, 5, 7, 8, 10)] if len(p) > 10 else
                  [int(p[0]) // 1000] + [float(p[i]) for i in (1, 2, 3, 4)] + [0, 0, 0, 0] for p in out])
    a = a[np.argsort(a[:, 0])]; _, u = np.unique(a[:, 0], return_index=True)
    return a[u]


def metrics(sym, days):
    """5-мин метрики: t (create_time), OI, OI в $, топ LSR по счетам, топ LSR по позициям, LSR по счетам, taker buy/sell."""
    import datetime
    out = []
    for d in days:
        for p in rows(fetch(f"daily/metrics/{sym}USDT/{sym}USDT-metrics-{d}.zip")) if False else _mrows(fetch(f"daily/metrics/{sym}USDT/{sym}USDT-metrics-{d}.zip")):
            try:
                t = int(datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp())
                out.append([t] + [float(x) if x else np.nan for x in p[2:8]])
            except ValueError:
                pass
    if not out: return None
    a = np.array(out); a = a[np.argsort(a[:, 0])]; _, u = np.unique(a[:, 0], return_index=True)
    return a[u]


def _mrows(data):
    if not data: return []
    z = zipfile.ZipFile(io.BytesIO(data))
    return [ln.split(",") for ln in z.read(z.namelist()[0]).decode().splitlines() if ln[:2] == "20"]


def kfull_spot(sym, days):
    out = []
    for d in days:
        data = fetch_spot(f"daily/klines/{sym}USDT/1m/{sym}USDT-1m-{d}.zip")
        out += rows(data)
    if not out: return None
    a = np.array([[int(p[0]) // (1000000 if len(p[0]) > 13 else 1000)] + [float(p[i]) for i in (1, 2, 3, 4, 5, 7, 8, 10)] for p in out])
    a = a[np.argsort(a[:, 0])]; _, u = np.unique(a[:, 0], return_index=True)
    return a[u]


def fetch_spot(path):
    global BASE
    return _fetch_base("https://data.binance.vision/data/spot", path)


def _fetch_base(base, path):
    fn = os.path.join(CACHE, "spot_" + path.replace("/", "_"))
    if os.path.exists(fn): return open(fn, "rb").read() or None
    tmp = f"{fn}.{threading.get_ident()}.tmp"
    for i in range(4):
        r = subprocess.run(["curl", "-sS", "-m", "60", "-w", "%{http_code}", "-o", tmp, f"{base}/{path}"], capture_output=True, text=True)
        if r.stdout == "404":
            open(fn, "wb").close()
            if os.path.exists(tmp): os.remove(tmp)
            return None
        if r.stdout == "200": os.replace(tmp, fn); return open(fn, "rb").read()
        time.sleep(2 + 2 * i)
    return None
