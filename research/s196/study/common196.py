"""s196 — общие функции проб: HTTP без ключей (User-Agent research-script/1.0), кэш в /home/user/mc_data/s196,
паузы при ошибках. Только охват данных, частоты и описание; доходы, цены после события и сделки НЕ считаются."""
import json
import os
import time
import urllib.error
import urllib.request

D = "/home/user/mc_data"
OUT = f"{D}/s196"
UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}
DAY = 86400
PERIODS = [("2020–2022", "2020-10-01", "2022-10-01"), ("2022–2024", "2022-10-01", "2024-10-01"),
           ("2024–2026", "2024-10-01", "2026-10-19")]


def http(url, data=None, headers=None, timeout=60, tries=5, raw=False):
    """GET/POST с повтором; 429 — пауза 30–60 с; прочие ошибки — 5, 10, 15… с. None после всех попыток."""
    h = dict(UA)
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        h.setdefault("Content-Type", "application/json")
    last = None
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout).read()
            return r if raw else json.loads(r)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (400, 401, 403, 404, 405, 410, 501):
                return None
            time.sleep(30 + 15 * i if e.code == 429 else 5 + 5 * i)
        except Exception as e:  # сеть, разбор
            last = repr(e)[:120]
            time.sleep(5 + 5 * i)
    print("  сбой:", url[:120], last, flush=True)
    return None


def cache_json(path, fn):
    """Кэш результата fn() в OUT/path (json)."""
    p = os.path.join(OUT, path)
    if os.path.exists(p):
        return json.load(open(p))
    v = fn()
    if v is not None:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(v, open(p, "w"))
    return v


def ts(s):
    import calendar
    return calendar.timegm(time.strptime(s[:10], "%Y-%m-%d"))


def period_of(t):
    for name, a, b in PERIODS:
        if ts(a) <= t < ts(b):
            return name
    return None


def months(name):
    for n, a, b in PERIODS:
        if n == name:
            return (ts(b) - ts(a)) / (30.4 * DAY)
