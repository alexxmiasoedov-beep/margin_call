"""s296 — минутные свечи Upbit и Bithumb на моменты входов 🇰🇷 (запись правил — ВЫВОДЫ.md).

Для каждого входа 🇰🇷 (s277, три периода) и биржи: KRW-BTC — закрытие минуты, кончающейся в te; монета — до 60 минутных
свечей до te (варианты рынка: тикер перпа и он же без приставки 1000…, как в s295). Upbit: `to` — UTC с «Z», Bithumb —
время Сеула без зоны. 404 — рынка нет. Выход — /home/user/mc_data/s296/kr_min.jsonl (дописывается, повтор продолжает).
Запуск: python3 -I research/s296/fetch.py"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s296/kr_min.jsonl"
PERS = ("2020–2022", "2022–2024", "2024–2026")
UA = {"User-Agent": "research-script/1.0"}
BASE = {"upbit": "https://api.upbit.com/v1/candles/minutes/1", "bithumb": "https://api.bithumb.com/v1/candles/minutes/1"}
RATE = {"upbit": 6.0, "bithumb": 6.0}
_lock = {ex: threading.Lock() for ex in BASE}
_last = {ex: 0.0 for ex in BASE}


def to_param(ex, te):
    if ex == "upbit":
        return pd.Timestamp(te, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ")
    return (pd.Timestamp(te, unit="s") + pd.Timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


def get(ex, market, te, count):
    url = f"{BASE[ex]}?{urllib.parse.urlencode(dict(market=market, to=to_param(ex, te), count=count))}"
    for i in range(6):
        with _lock[ex]:
            w = _last[ex] + 1.0 / RATE[ex] - time.time()
            if w > 0:
                time.sleep(w)
            _last[ex] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 400:
                return None
            time.sleep(1 + 2 * i)
        except Exception:
            time.sleep(1 + 2 * i)
    raise RuntimeError(f"не скачалось: {url}")


def parse(rows, te):
    out = []
    if not isinstance(rows, list):
        return out
    for r in rows:
        if not isinstance(r, dict) or "candle_date_time_utc" not in r:
            continue
        st = int(pd.Timestamp(r["candle_date_time_utc"], tz="UTC").timestamp())
        out.append((st, float(r["trade_price"]), float(r["candle_acc_trade_price"])))
    return out


_btc = {}


def btc(ex, te):
    k = (ex, te)
    if k not in _btc:
        c = parse(get(ex, "KRW-BTC", te, 1), te)
        _btc[k] = [c[0][0], c[0][1]] if c else None
    return _btc[k]


def one_ex(ex, s, te):
    m0 = re.match(r"^(1000000|100000|10000|1000)(.+)$", s)
    cands = [(s, 1.0)] + ([(m0.group(2), float(m0.group(1)))] if m0 else [])
    res = []
    for b, m in cands:
        rows = get(ex, f"KRW-{b}", te, 60)
        c = parse(rows, te)
        if c:
            res.append(dict(b=b, m=m, st=c[0][0], c=c[0][1], v60=sum(v for st, p, v in c if st >= te - 3600)))
    if not res:
        return None
    return dict(btc=btc(ex, te), coin=res)


def one(r):
    per, s, te = r
    out = dict(per=per, s=s, te=te)
    try:
        with ThreadPoolExecutor(2) as ex2:
            fu = {ex: ex2.submit(one_ex, ex, s, te) for ex in BASE}
            for ex, f in fu.items():
                out[ex] = f.result()
    except Exception as e:
        out["err"] = f"{type(e).__name__}: {e}"[:200]
    return out


def main():
    rows = []
    for per in PERS:
        R = pd.read_pickle(f"{D}/s277_{per}.pkl")
        g = R[(R.h == "🇰🇷") & (R.ex == "8 ч")]
        rows += [(per, str(s), int(te)) for s, te in zip(g.s, g.te)]
    done = set()
    if os.path.exists(OUT):
        for ln in open(OUT):
            d = json.loads(ln)
            if "err" not in d:
                done.add((d["per"], d["s"], d["te"]))
    todo = [r for r in rows if r not in done]
    print(f"входов {len(rows)}, готово {len(done)}, осталось {len(todo)}", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex, open(OUT, "a") as fo:
        for i, d in enumerate(ex.map(one, todo)):
            fo.write(json.dumps(d, ensure_ascii=False) + "\n"); fo.flush()
            if i % 200 == 0:
                print(f"  {i}/{len(todo)} {time.time() - t0:.0f} с {d.get('err', '')}", flush=True)
    print(f"готово за {time.time() - t0:.0f} с", flush=True)


if __name__ == "__main__":
    main()
