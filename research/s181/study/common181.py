"""s181 — общие функции проб: вселенная перпов Binance USDT-M по периодам, базовый тикер, HTTP с паузами.
Только частоты и охват данных: доходы, цены после событий и сделки не считаются."""
import gzip
import json
import os
import pickle
import re
import time
import urllib.error
import urllib.request

D = "/home/user/mc_data"
OUT = f"{D}/s181"
UA = {"User-Agent": "research-script/1.0", "Accept-Encoding": "gzip"}
PER = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"),
       "2024–2026": ("2024-10-01", "2026-11-01")}
MULT = re.compile(r"^(1000000|100000|10000|1000|100|1M)(?=[A-Z])")


def base(perp):
    """1000PEPE → PEPE, 1000000MOG → MOG, 1MBABYDOGE → BABYDOGE."""
    return MULT.sub("", perp)


def perps():
    """{перп: [(начало, конец) по файлам фандинга]} без акций и металлов (s12/perp_kind.pkl, ключ tradfi)."""
    kind = pickle.load(open(f"{D}/s12/perp_kind.pkl", "rb"))
    out = {}
    for p in (f"{D}/s117/fund_2020.pkl", f"{D}/s117/fund_oos.pkl", f"{D}/s2/fund2y.pkl"):
        F = pickle.load(open(p, "rb"))
        for k, a in F.items():
            if k in kind["tradfi"] or not len(a):
                continue
            out.setdefault(k, []).append((float(a[0, 0]), float(a[-1, 0])))
    return out


def alive(spans, t, pad=2 * 86400):
    """Перп торговался в момент t (секунды) — внутри одного из отрезков файлов фандинга; после 30.09.2026 — живой,
    если был жив в конце последнего файла."""
    for a, b in spans:
        if a - pad <= t <= b + pad:
            return True
    last = max(b for _, b in spans)
    return t > last and last >= 1790700000          # файл 2024–2026 кончается 30.09.2026


def get(url, data=None, headers=None, tries=5, timeout=120, ok=(200,)):
    """GET/POST с паузой и повтором при сбое сети; 400/402/403/404 — без повтора."""
    h = dict(UA)
    if headers:
        h.update(headers)
    last = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return r.status, raw
        except urllib.error.HTTPError as e:
            last = e.code
            if e.code in (400, 401, 402, 403, 404):
                return e.code, b""
            time.sleep(60 if e.code == 429 else 5 * (a + 1))
        except Exception as e:  # сеть: пауза и повтор, без циклов вхолостую
            last = type(e).__name__
            time.sleep(5 * (a + 1))
    return last, b""


def jload(path):
    if path.endswith(".gz"):
        return json.load(gzip.open(path, "rt"))
    return json.load(open(path))


def jsave(obj, path):
    tmp = path + ".tmp"
    if path.endswith(".gz"):
        with gzip.open(tmp, "wt") as f:
            json.dump(obj, f)
    else:
        with open(tmp, "w") as f:
            json.dump(obj, f)
    os.replace(tmp, path)


def month_counts(times, per):
    """Событий в месяц за период: число / месяцев периода."""
    import pandas as pd
    t0, t1 = (pd.Timestamp(x, tz="UTC").timestamp() for x in PER[per])
    n = sum(1 for t in times if t0 <= t < t1)
    return n / ((t1 - t0) / (30.4 * 86400))
