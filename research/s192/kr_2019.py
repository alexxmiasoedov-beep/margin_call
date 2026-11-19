"""s192 — часовые свечи рынков к воне Upbit и Bithumb за 01.09.2019–04.10.2020 для монет с перпом Binance в периоде
(k_2019.pkl). Логика и формат — как s88/oos_fetch.py (kr): свечи 60 мин назад от T1 по 200, файл
kc/<биржа>/KRW-<монета>.pkl = {t (начало часа, сек), c (закрытие, вона), v (оборот, вона)} или None (рынка в периоде
не было), map.pkl = {монета: перп + "USDT"}. KRW-BTC Upbit — для курса воны.

Рынки: текущие списки KRW обеих бирж ∩ монеты перпов периода; дополнительно монеты перпов, которых сейчас нет
в списке биржи, — попытка запросить снятый рынок (API таких обычно не отдаёт: 404 или пусто — так и записывается
в kr_2019_status.json). Паузы: Upbit — 2 потока, Bithumb — 3, после каждого запроса 0,15 с; сбой не кэшируется.
User-Agent — «research-script/1.0». Запуск: python3 <repo>/research/s192/kr_2019.py"""
import datetime
import json
import os
import pickle
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
from kr_listings import API, iso, utc  # noqa: E402

UTC = datetime.timezone.utc
OUT = "/home/user/mc_data/s192"
T0, T1 = datetime.datetime(2019, 9, 1, tzinfo=UTC), datetime.datetime(2020, 10, 4, tzinfo=UTC)
UA = "research-script/1.0"
RENAME = {"EOS": "A"}           # рынок переименован, история под новым кодом сохранилась (EOS → Vaulta, KRW-A, проверено ценой)
STABLE = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "PYUSD", "RLUSD", "BUSD", "UST"}


def get(url):
    """Список из JSON; None — нет рынка (400/404) или сбой после повторов."""
    for i in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                x = json.loads(r.read().decode())
            if isinstance(x, list):
                return x
            err = x.get("error") if isinstance(x, dict) else None
            if isinstance(err, dict) and (str(err.get("name")) == "404" or "not found" in str(err.get("message", "")).lower()):
                return None                                     # Bithumb: «Code not found» в теле ответа с кодом 200
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            time.sleep(5 if e.code == 429 else 1.5 * (i + 1))
            continue
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return None


def kr(ex, market):
    """Как s88/oos_fetch.kr: True — записано (в том числе «рынка нет»), False — сбой посреди ряда (повторить).
    Файл — по монете перпа (KRW-EOS), запрос — по нынешнему коду рынка (KRW-A, RENAME)."""
    path = f"{OUT}/kc/{ex}/{market}.pkl"
    if os.path.exists(path):
        return True
    code = "KRW-" + RENAME.get(market[4:], market[4:])
    rows, to = {}, T1
    while to > T0:
        c = get(f"{API[ex]}/v1/candles/minutes/60?market={code}&count=200&to={iso(to, ex)}")
        time.sleep(0.15)
        if c is None and rows:
            return False
        if not c:
            break
        for x in c:
            rows[int(utc(x).timestamp())] = (float(x["trade_price"]), float(x["candle_acc_trade_price"]))
        first = min(utc(x) for x in c)
        if len(c) < 200 or first >= to:
            break
        to = first
    res = None
    if rows:
        t = np.array(sorted(rows), dtype=np.int64)
        res = {"t": t, "c": np.array([rows[x][0] for x in t]), "v": np.array([rows[x][1] for x in t])}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pickle.dump(res, open(path + ".tmp", "wb")); os.replace(path + ".tmp", path)
    return True


def main():
    K = pickle.load(open(f"{OUT}/k_2019.pkl", "rb"))
    perps = sorted(K)
    del K
    listed = {}
    for ex in API:
        ms = get(f"{API[ex]}/v1/market/all") or []
        listed[ex] = {m["market"][4:] for m in ms if m["market"].startswith("KRW-")}
        print(ex, "рынков к воне сейчас:", len(listed[ex]), flush=True)
    base2perp = {}
    for p in perps:
        b = p
        for pre in ("1000000", "1000"):
            if p.startswith(pre) and len(p) > len(pre):
                b = p[len(pre):]
        if b not in STABLE:
            base2perp.setdefault(b, p)
    jobs, kind = [], {}
    for b in sorted(base2perp):
        for ex in sorted(API):
            jobs.append((ex, f"KRW-{b}"))
            kind[(ex, b)] = "listed" if RENAME.get(b, b) in listed[ex] else "delisted?"
    for b, nb in RENAME.items():                                      # кэш старого запроса по прежнему коду — заново
        for ex in API:
            pth = f"{OUT}/kc/{ex}/KRW-{b}.pkl"
            if os.path.exists(pth) and pickle.load(open(pth, "rb")) is None:
                os.remove(pth)
    print(f"перпов периода {len(perps)}, монет {len(base2perp)}; запросов рынков {len(jobs)} "
          f"(в текущих списках: Upbit {sum(1 for b in base2perp if RENAME.get(b, b) in listed['upbit'])}, "
          f"Bithumb {sum(1 for b in base2perp if RENAME.get(b, b) in listed['bithumb'])}); переименования {RENAME}", flush=True)
    for rnd in range(3):
        with ThreadPoolExecutor(2) as pu, ThreadPoolExecutor(3) as pb:
            fs = [(pu if ex == "upbit" else pb).submit(kr, ex, m) for ex, m in jobs]
            bad = [j for j, f in zip(jobs, fs) if not f.result()]
        print(f"проход {rnd + 1}: не скачано рынков {len(bad)}", flush=True)
        if not bad:
            break
        jobs = bad
        time.sleep(60)
    status, mp = {}, {}
    for (ex, b), kd in kind.items():
        path = f"{OUT}/kc/{ex}/KRW-{b}.pkl"
        x = pickle.load(open(path, "rb")) if os.path.exists(path) else "сбой"
        if isinstance(x, dict):
            t = x["t"]
            day = lambda x: datetime.datetime.fromtimestamp(int(x), UTC).strftime("%Y-%m-%d")  # noqa: E731
            st = dict(kind=kd, code="KRW-" + RENAME.get(b, b), hours=int(len(t)), first=day(t[0]), last=day(t[-1]))
            mp[b] = base2perp[b] + "USDT"
        else:
            st = dict(kind=kd, hours=0, note=x if isinstance(x, str) else "нет свечей в периоде")
        status[f"{ex}:KRW-{b}"] = st
    pickle.dump(mp, open(f"{OUT}/map.pkl", "wb"))
    json.dump(status, open(f"{OUT}/kr_2019_status.json", "w"), ensure_ascii=False, indent=1)
    for ex in API:
        with_data = [k for k, v in status.items() if k.startswith(ex) and v["hours"] > 0]
        dl = [k for k in with_data if status[k]["kind"] != "listed"]
        print(f"{ex}: рынков со свечами в периоде {len(with_data)} (из них не в текущем списке {len(dl)}: {dl})", flush=True)
    print("монет с рынком к воне (map.pkl):", len(mp), sorted(mp), flush=True)


if __name__ == "__main__":
    main()
