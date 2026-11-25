"""s297 — изучение: минутная структура корейских скачков вокруг входов ⏰ и 🇰🇷 (Upbit, Bithumb, перп Binance).

Для каждого входа (⏰ — s294/g7_<период>.pkl, 🇰🇷 — s277) — минутные свечи за [te − 160 мин, te + 240 мин):
Upbit и Bithumb (`/v1/candles/minutes/1`, два запроса по 200; функции s296/fetch.py; рынок — тикер перпа или он же без
приставки 1000…), перп Binance — дневные архивы 1m data.binance.vision. Доходы здесь не считаются.
Выход — /home/user/mc_data/s297/min.pkl: {(журнал, период, монета, te): {up, bt: [[начало, o, h, l, c, оборот KRW]],
bn: [[начало, o, h, l, c, qv, tbq]], b, m}}. Повторный запуск продолжает. Запуск: python3 -I research/s297/collect.py"""
import importlib.util
import io
import os
import pickle
import re
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s297/min.pkl"
PERS = ("2020–2022", "2022–2024", "2024–2026")
UA = {"User-Agent": "research-script/1.0"}
spec = importlib.util.spec_from_file_location("f296", "/home/user/margin_call/research/s296/fetch.py")
F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)


def kr_series(ex, s, te):
    m0 = re.match(r"^(1000000|100000|10000|1000)(.+)$", s)
    for b, m in [(s, 1.0)] + ([(m0.group(2), float(m0.group(1)))] if m0 else []):
        rows = []
        for to in (te + 240 * 60, te + 40 * 60):
            r = F.get(ex, f"KRW-{b}", to, 200)
            if not isinstance(r, list):
                break
            for x in r:
                if isinstance(x, dict) and "candle_date_time_utc" in x:
                    st = int(pd.Timestamp(x["candle_date_time_utc"], tz="UTC").timestamp())
                    rows.append((st, float(x["opening_price"]), float(x["high_price"]), float(x["low_price"]),
                                 float(x["trade_price"]), float(x["candle_acc_trade_price"])))
        if rows:
            a = np.array(sorted(set(rows)))
            return b, m, a[(a[:, 0] >= te - 160 * 60) & (a[:, 0] < te + 240 * 60)]
    return None, None, None


_bn = {}


def bn_day(sym, day):
    k = (sym, day)
    if k in _bn:
        return _bn[k]
    url = f"https://data.binance.vision/data/futures/um/daily/klines/{sym}/1m/{sym}-1m-{day}.zip"
    out = None
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines():
                p = ln.split(",")
                if p and p[0][:1].isdigit():
                    rows.append((int(p[0]) // 1000, float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[7]), float(p[10])))
            out = np.array(rows)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
        except Exception:
            time.sleep(2 + 3 * i)
    if len(_bn) > 4000:
        _bn.clear()
    _bn[k] = out
    return out


def bn_series(s, te):
    days = sorted({pd.Timestamp(t, unit="s").strftime("%Y-%m-%d") for t in (te - 160 * 60, te + 240 * 60 - 1)})
    parts = [x for d in days if (x := bn_day(f"{s}USDT", d)) is not None and len(x)]
    if not parts:
        return None
    a = np.concatenate(parts)
    return a[(a[:, 0] >= te - 160 * 60) & (a[:, 0] < te + 240 * 60)]


def one(r):
    j, per, s, te = r
    out = {}
    try:
        with ThreadPoolExecutor(3) as ex:
            fu = ex.submit(kr_series, "upbit", s, te); fb = ex.submit(kr_series, "bithumb", s, te); fn = ex.submit(bn_series, s, te)
            bu, mu, au = fu.result(); bb, mb, ab = fb.result(); out["bn"] = fn.result()
        out.update(up=au, bt=ab, b=bu or bb, m=mu or mb)
    except Exception as e:
        out["err"] = f"{type(e).__name__}: {e}"[:200]
    return r, out


def main():
    ev = []
    for per in PERS:
        g = pd.read_pickle(f"{D}/s294/g7_{per}.pkl")
        ev += [("⏰", per, str(s), int(te)) for s, te in zip(g.s, g.te)]
        R = pd.read_pickle(f"{D}/s277_{per}.pkl")
        k = R[(R.h == "🇰🇷") & (R.ex == "8 ч")]
        ev += [("🇰🇷", per, str(s), int(te)) for s, te in zip(k.s, k.te)]
    res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
    todo = [e for e in ev if e not in res or "err" in res[e]]
    print(f"входов {len(ev)}, готово {len(ev) - len(todo)}, осталось {len(todo)}", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        for i, (r, o) in enumerate(ex.map(one, todo)):
            res[r] = o
            if i % 250 == 0:
                print(f"  {i}/{len(todo)} {time.time() - t0:.0f} с {o.get('err', '')}", flush=True)
                pickle.dump(res, open(OUT + ".tmp", "wb")); os.replace(OUT + ".tmp", OUT)
    pickle.dump(res, open(OUT + ".tmp", "wb")); os.replace(OUT + ".tmp", OUT)
    print(f"готово за {time.time() - t0:.0f} с", flush=True)


if __name__ == "__main__":
    main()
