"""s147 — фандинг Gate, KuCoin и Hyperliquid вокруг начислений Binance ≤ −0,3% (гипотеза — ВЫВОДЫ.md). Для каждой монеты
скачиваются только месяцы, где у неё есть такое начисление Binance (± сутки). Итог — /home/user/mc_data/s147/<площадка>.pkl:
{монета Binance: {время начисления, с: ставка}}; отдельно — список монет, которых на площадке нет. Прерванный сбор
продолжается. Бережно: Gate — статические файлы в 4 потока, KuCoin — 4 запроса в секунду, HL — 1 запрос в секунду.
Запуск: python3 <repo>/research/s147/gap_fetch.py gate|kucoin|hl"""
import gzip
import json
import os
import pickle
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

DATA, H1, DAY = "/home/user/mc_data", 3600, 86400
UA = {"User-Agent": "research-script/1.0"}
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "s117/fund_2020.pkl"),
       "2022–2024": ("2022-10-01", "2024-10-01", "s117/fund_oos.pkl"),
       "2024–2026": ("2024-10-01", "2026-10-17", "s2/fund2y.pkl")}
NEG = -0.003


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def binance_funding(per):
    """{монета: массив [время с, ставка]} периода; для 2024–2026 гг. — ещё месяцы 2026-09/10 из кэша s15/fund."""
    FU = pickle.load(open(os.path.join(DATA, PER[per][2]), "rb"))
    out = {}
    for s, f in FU.items():
        rows = [(int(r[0]), float(r[2])) for r in f]
        if per == "2024–2026":
            last = max((r[0] for r in rows), default=0)
            for m in ("2026-09", "2026-10"):
                p = os.path.join(DATA, f"s15/fund/{s}-{m}.csv")
                if os.path.exists(p):
                    for ln in open(p).read().splitlines():
                        q = ln.split(",")
                        if q and q[0].isdigit() and int(q[0]) // 1000 > last:
                            rows.append((int(q[0]) // 1000, float(q[2])))
        if rows:
            out[s] = np.array(sorted(set(rows)), float)
    return out


def events(fr, t0=None, t1=None, neg=NEG):
    """Начисления Binance ≤ neg: прошлое 4–8 ч назад, следующее не раньше T + 2 ч 15 мин → [(T, ставка, интервал с)]."""
    t, r = fr[:, 0], fr[:, 1]
    out = []
    for i in np.flatnonzero(r <= neg):
        if i == 0 or i + 1 >= len(t):
            continue
        dt0, dt1 = t[i] - t[i - 1], t[i + 1] - t[i]
        if 4 * H1 - 60 <= dt0 <= 8 * H1 + 60 and dt1 >= 2.25 * H1 and (t0 is None or t0 <= t[i] < t1):
            out.append((int(t[i]), float(r[i]), int(dt0)))
    return out


def need(unit="month"):
    """{монета: множество месяцев ГГГГММ (месяц T − сутки, T, T + сутки)} — для Gate и KuCoin; для HL (unit="day") —
    сутки ГГГГММДД, в которые попадает окно (T − 8 ч, T], только с 05.2023: у HL ставка каждый час, присутствие видно
    по тому же окну."""
    M = {}
    for per, (a, b, _) in PER.items():
        for s, fr in binance_funding(per).items():
            for T, _, _ in events(fr, ts(a), ts(b)):
                if unit == "day":
                    if T >= ts("2023-05-01"):
                        for x in (T - 8 * H1, T):
                            M.setdefault(s, set()).add(pd.Timestamp(x, unit="s").strftime("%Y%m%d"))
                    continue
                for x in (T - DAY, T, T + DAY):
                    M.setdefault(s, set()).add(pd.Timestamp(x, unit="s").strftime("%Y%m"))
    return M


def names(s, venue):
    base = [s]
    for p in ("1000000", "1000", "1M"):
        if s.startswith(p) and len(s) > len(p):
            base.append(s[len(p):])
            break
    if venue == "kucoin":
        return [("XBT" if b == "BTC" else b) + "USDTM" for b in base]
    if venue == "hl":                                              # 1000PEPE → kPEPE, 1000000MOG → MOG
        if s.startswith("1000000"):
            return [s[7:]]
        return ["k" + s[4:]] if s.startswith("1000") else [s]
    return [b + "_USDT" for b in base]


def http(req, tries=4):
    for k in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=40).read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 400, 500):
                return e.code
            time.sleep(5 + 10 * k)
        except Exception:
            time.sleep(5 + 10 * k)
    return None


def month_bounds(ym):
    if "-" in ym:                                                  # сутки ГГГГММДД-ГГГГММДД включительно
        a, b = (pd.Timestamp(f"{x[:4]}-{x[4:6]}-{x[6:]}", tz="UTC") for x in ym.split("-"))
        return int(a.timestamp()), int(b.timestamp()) + DAY
    if len(ym) == 8:                                               # сутки ГГГГММДД
        a = pd.Timestamp(f"{ym[:4]}-{ym[4:6]}-{ym[6:]}", tz="UTC")
        return int(a.timestamp()), int(a.timestamp()) + DAY
    a = pd.Timestamp(f"{ym[:4]}-{ym[4:]}-01", tz="UTC")
    return int(a.timestamp()), int((a + pd.offsets.MonthBegin(1)).timestamp())


def fetch_gate(s, ym, nm):
    b = http(urllib.request.Request(f"https://download.gatedata.org/futures_usdt/funding_applies/{ym}/{nm}-{ym}.csv.gz",
                                    headers=UA))
    if b is None:
        return None
    if isinstance(b, int):
        return []
    rows = []
    for ln in gzip.decompress(b).decode().splitlines():
        q = ln.split(",")
        if len(q) >= 2 and q[0].isdigit():
            rows.append((int(q[0]), float(q[1])))
    return rows


def fetch_kucoin(s, ym, nm):
    a, b = month_bounds(ym)
    rows, step = [], 31 * DAY
    x = a
    while x < b:
        y = min(x + step, b)
        raw = http(urllib.request.Request(
            f"https://api-futures.kucoin.com/api/v1/contract/funding-rates?symbol={nm}&from={x * 1000}&to={y * 1000 - 1}",
            headers=UA))
        time.sleep(0.25)
        if raw is None:
            return None
        if isinstance(raw, int):
            return []
        d = json.loads(raw)
        if d.get("code") != "200000":
            return []
        z = d.get("data") or []
        if len(z) >= 100 and step > DAY:                         # упор в предел ответа — окно короче
            step //= 2
            continue
        rows += [(int(w["timepoint"]) // 1000, float(w["fundingRate"])) for w in z]
        x = y
    return rows


def fetch_hl(s, ym, nm):
    a, b = month_bounds(ym)
    rows, x = [], a * 1000
    while x < b * 1000:
        raw = http(urllib.request.Request("https://api.hyperliquid.xyz/info", data=json.dumps(
            {"type": "fundingHistory", "coin": nm, "startTime": x, "endTime": b * 1000 - 1}).encode(),
            headers={"Content-Type": "application/json", **UA}))
        time.sleep(1.1 + len(json.loads(raw) or []) / 400 if isinstance(raw, bytes) else 1.1)  # вес 20 + 1 за 20 записей, 1200 в мин
        if raw == 500:                     # монеты на HL нет (или сбой) — проверить ещё раз
            time.sleep(2)
            raw = http(urllib.request.Request("https://api.hyperliquid.xyz/info", data=json.dumps(
                {"type": "fundingHistory", "coin": nm, "startTime": x, "endTime": b * 1000 - 1}).encode(),
                headers={"Content-Type": "application/json", **UA}))
            time.sleep(1.1)
            if raw == 500:
                return "MISSING"
        if raw is None:
            return None
        if isinstance(raw, int):
            return []
        z = json.loads(raw) or []
        if not z:
            break
        rows += [(int(w["time"]) // 1000, float(w["fundingRate"])) for w in z]
        if len(z) < 500:
            break
        x = int(z[-1]["time"]) + 1
    return rows


def main(venue):
    os.makedirs(os.path.join(DATA, "s147"), exist_ok=True)
    path = os.path.join(DATA, f"s147/{venue}.pkl")
    st = pickle.load(open(path, "rb")) if os.path.exists(path) else {"rows": {}, "done": set(), "missing": set(), "name": {}}
    M = need("day" if venue == "hl" else "month")
    if venue == "hl":                      # соседние сутки (разрыв ≤ 3 сут) — одним окном до 20 сут: вес запроса меньше
        R = {}
        for c, days in M.items():
            d = sorted(pd.Timestamp(x, tz="UTC") for x in days)
            a = b = d[0]
            for x in d[1:]:
                if (x - b).days <= 3 and (x - a).days < 20:
                    b = x
                else:
                    R.setdefault(c, set()).add(f"{a:%Y%m%d}-{b:%Y%m%d}"); a = b = x
            R.setdefault(c, set()).add(f"{a:%Y%m%d}-{b:%Y%m%d}")
        M = R
    todo = [(s, ym) for s in sorted(M) for ym in sorted(M[s]) if (s, ym) not in st["done"] and (s, ym[:6]) not in st["done"]]
    print(venue, "монето-месяцев к скачиванию", len(todo), flush=True)
    fn = {"gate": fetch_gate, "kucoin": fetch_kucoin, "hl": fetch_hl}[venue]

    def one(item):
        s, ym = item
        if s in st["missing"]:
            return s, ym, None, "missing"
        cand = [st["name"][s]] if s in st["name"] else names(s, venue)
        for nm in cand:
            r = fn(s, ym, nm)
            if r is None:
                return s, ym, None, "error"
            if r == "MISSING":
                return s, ym, None, "missing_now"
            if r:
                return s, ym, (nm, r), "ok"
        return s, ym, None, "empty"

    n = 0
    workers = {"gate": 4, "kucoin": 4, "hl": 1}[venue]
    with ThreadPoolExecutor(workers) as ex:
        for s, ym, res, why in ex.map(one, todo):
            if why == "error":
                continue
            if why == "missing_now":
                st["missing"].add(s)
            st["done"].add((s, ym))
            if res:
                nm, r = res
                st["name"][s] = nm
                st["rows"].setdefault(s, {}).update(dict(r))
            n += 1
            if n % 50 == 0:
                pickle.dump(st, open(path, "wb")); print(venue, n, "из", len(todo), "монет с данными", len(st["rows"]),
                                                         flush=True)
    # монета ни разу не нашлась на площадке — пометить, чтобы не спрашивать снова
    for s in M:
        if s not in st["rows"] and all((s, ym) in st["done"] for ym in M[s]):
            st["missing"].add(s)
    pickle.dump(st, open(path, "wb"))
    print(venue, "готово: монет с данными", len(st["rows"]), "без данных", len(st["missing"]), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
