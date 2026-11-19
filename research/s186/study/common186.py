"""s186 — общие функции проб: HTTP с паузами, кэш, периоды и вселенная перпов (через common183), токены с плечом.

Только списки, охват, частоты событий-кандидатов, размеры потоков ребаланса и пересечения. Доходы после момента
сигнала, сделки и плацебо НЕ считаются (правило «гипотезы — до проверки»)."""
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "s183", "study"))
import common183 as C3  # noqa: E402,F401  (периоды, свечи, журналы)

D = "/home/user/mc_data"
OUT = f"{D}/s186"
RAW = f"{OUT}/raw"
os.makedirs(RAW, exist_ok=True)
UA = {"User-Agent": "research-script/1.0", "Accept-Encoding": "gzip"}
DAY = 86400
PER = C3.PER
PERS = C3.PERS
LT_RE = re.compile(r"^(.+?)(\d+)(L|S)$")          # BTC3L, SOL5S, …


def get(url, data=None, headers=None, tries=4, timeout=90):
    """GET/POST с паузой и повтором при сбое сети; 400/401/402/403/404 — без повтора."""
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


def jget(url, cache=None, **kw):
    """JSON с кэшем в RAW (имя файла cache); при сбое — None."""
    if cache:
        p = f"{RAW}/{cache}"
        if os.path.exists(p):
            return json.load(open(p))
    code, raw = get(url, **kw)
    if code != 200 or not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    if cache:
        tmp = f"{RAW}/{cache}.tmp"
        json.dump(obj, open(tmp, "w"))
        os.replace(tmp, f"{RAW}/{cache}")
    return obj


def ts(x):
    return C3.ts(x)


def iso(t):
    import datetime as dt
    return dt.datetime.fromtimestamp(int(t), dt.UTC).strftime("%Y-%m-%d")


class Log:
    """Печать и запись в <скрипт>.log рядом со скриптом."""

    def __init__(self, name):
        self.f = open(os.path.join(HERE, name + ".log"), "w")

    def __call__(self, *a):
        s = " ".join(str(x) for x in a)
        print(s)
        self.f.write(s + "\n")
        self.f.flush()
