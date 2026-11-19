"""s192 — четвёртый независимый период: 15-мин свечи и фандинг всех USDT-M перпов Binance за 09.2019–09.2020
в формате s117/k_2020.pkl и s117/fund_2020.pkl → /home/user/mc_data/s192/k_2019.pkl, fund_2019.pkl.

Источники (без ключей):
- архив data.binance.vision (кэш research/futures/bv.py в /home/user/mc_data/s192/cache): месяцы 2020-01 … 2020-09.
  Архив USDT-M начинается с 01.2020 — до этого перпов было три (BTC с 08.09.2019, ETH с 27.11.2019, BCH с 12.2019);
- месяцы 09–12.2019 этих перпов — публичный адрес www.binance.com/fapi/v1/klines и …/fundingRate (fapi.binance.com
  из облака закрыт, 451). На пересечении (01.01.2020) ответы сверяются с архивом.
Список символов — весь листинг архива (как s117), в период попадают символы с месячными файлами 2020-01 … 2020-09.
Формат как s117: {монета без USDT: {t int64, o, h, l, c, qv, tb, n float32}}; монеты дополнены до общей сетки 15 мин
(от первой свечи BTC до 30.09.2020 23:45) заглушками без объёма с последней ценой (до начала торгов — с первой).
Фандинг: {монета: массив [время сек, интервал ч, ставка]}.
Запуск: python3 <repo>/research/s192/load_2019.py   (сам переходит в /home/user/mc_data/s192)"""
import datetime
import json
import os
import pickle
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

OUT = "/home/user/mc_data/s192"
os.makedirs(OUT, exist_ok=True)
os.chdir(OUT)                                                     # кэш bv.py — относительный «cache/»
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "futures"))
import bv  # noqa: E402

UA = "research-script/1.0"
API = "https://www.binance.com/fapi/v1"
ARCH = [f"2020-{m:02d}" for m in range(1, 10)]                    # месяцы архива
T_API0 = int(datetime.datetime(2019, 9, 1, tzinfo=datetime.timezone.utc).timestamp())
T_ARCH0 = int(datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc).timestamp())
T_END = int(datetime.datetime(2020, 10, 1, tzinfo=datetime.timezone.utc).timestamp())   # конец периода (не включая)
_lock = threading.Lock()
_last = [0.0]


def log(*a):
    print(datetime.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def s3_list(prefix):
    keys, marker = [], ""
    while True:
        url = f"https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix={prefix}&delimiter=/" + \
              (f"&marker={marker}" if marker else "")
        x = ""
        for i in range(4):
            r = subprocess.run(["curl", "-sS", "-m", "60", url], capture_output=True, text=True)
            x = r.stdout
            if "<ListBucketResult" in x:
                break
            time.sleep(3 * (i + 1))
        got = re.findall(r"<Key>([^<]+)</Key>", x) + re.findall(r"<Prefix>([^<]+)</Prefix>", x)[1:]
        keys += got
        if "<IsTruncated>true" not in x or not got:
            return keys
        nm = re.findall(r"<NextMarker>([^<]+)</NextMarker>", x)
        marker = nm[0] if nm else max(got)


def symbols():
    """Все символы USDT-M архива с суффиксом USDT (как s117/load_oos.symbols)."""
    p = s3_list("data/futures/um/monthly/klines/")
    syms = re.findall(r"klines/([A-Z0-9]+)/$", "\n".join(p), re.M)
    return sorted({s[:-4] for s in syms if s.endswith("USDT")})


def months_of(s):
    keys = s3_list(f"data/futures/um/monthly/klines/{s}USDT/15m/{s}USDT-15m-2020-0")
    return sorted({m for m in re.findall(r"-15m-(2020-0\d)\.zip$", "\n".join(keys), re.M) if m in ARCH})


def cached(name, fn):
    """Ответы API кэшируются в api_cache/<name>.json (повторный запуск не ходит в сеть)."""
    os.makedirs("api_cache", exist_ok=True)
    p = f"api_cache/{name}.json"
    if os.path.exists(p):
        return json.load(open(p))
    x = fn()
    json.dump(x, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
    return x


def api(path):
    """GET к www.binance.com/fapi с паузой ≥ 0,4 с между запросами (общая на все потоки); None — нет символа (400/404)."""
    for i in range(6):
        with _lock:
            w = 0.4 - (time.time() - _last[0])
            if w > 0:
                time.sleep(w)
            _last[0] = time.time()
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            time.sleep(60 if e.code in (418, 429) else 5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"нет ответа: {path}")


def api_klines(s, t0, t1):
    """15-мин свечи [t0, t1) с API: строки как в архиве (t мс, o, h, l, c, v, t закр., qv, n, tb_base, tb_quote)."""
    out, st = [], t0 * 1000
    while st < t1 * 1000:
        x = api(f"/klines?symbol={s}USDT&interval=15m&startTime={st}&endTime={t1 * 1000 - 1}&limit=1500")
        if not x:
            break
        out += x
        nxt = int(x[-1][0]) + 900_000
        if nxt <= st or len(x) < 1500:
            break
        st = nxt
    return out


def api_funding(s, t0, t1):
    out, st = [], t0 * 1000
    while st < t1 * 1000:
        x = api(f"/fundingRate?symbol={s}USDT&startTime={st}&endTime={t1 * 1000 - 1}&limit=1000")
        if not x:
            break
        out += [(int(r["fundingTime"]) // 1000, float(r["fundingRate"])) for r in x]
        nxt = int(x[-1]["fundingTime"]) + 1
        if len(x) < 1000:
            break
        st = nxt
    return [list(x) for x in sorted(set(out))]


def to_rows(api_rows):
    """Строки API → массив как bv.kfull: [t сек, o, h, l, c, volume, quote_volume, trades, taker_buy_quote]."""
    return np.array([[int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]), float(r[7]),
                      float(r[8]), float(r[10])] for r in api_rows], dtype=np.float64).reshape(-1, 9)


def one(s):
    ms = months_of(s)
    if not ms:
        return s, None, None, None
    k = bv.kfull(s, "klines", "15m", ms)
    fr = []
    for m in ms:
        for p in bv.rows(bv.fetch(f"monthly/fundingRate/{s}USDT/{s}USDT-fundingRate-{m}.zip")):
            try:
                fr.append((int(p[0]) // 1000, float(p[1]), float(p[2])))
            except (ValueError, IndexError):
                pass
    info = dict(months=ms, api_k=0, api_f=0)
    # перп торговался до 2020 г. (первая свеча архива — 01.01.2020 00:00) → 09–12.2019 с API
    if k is not None and len(k) and int(k[0, 0]) == T_ARCH0:
        ak = cached(f"{s}_klines_2019", lambda: api_klines(s, T_API0, T_ARCH0))
        if ak:
            a = to_rows(ak)
            k = np.vstack([a, k])
            k = k[np.argsort(k[:, 0], kind="stable")]
            _, u = np.unique(k[:, 0], return_index=True)
            k = k[u]
            info["api_k"] = len(a)
        af = cached(f"{s}_funding_2019", lambda: api_funding(s, T_API0, T_ARCH0))
        if af:
            tt = np.array([x[0] for x in af])
            info["api_f"] = len(af)
            info["api_f_steps_h"] = sorted({int(round(d / 3600)) for d in np.diff(tt)})   # в 2019 г. — 8 ч
            fr += [(int(t), 8.0, float(r)) for t, r in af]
    if k is None or len(k) < 96 * 3:
        return s, None, (np.array(sorted(fr)) if fr else None), info
    k = k[k[:, 0] < T_END]
    arr = dict(t=k[:, 0].astype(np.int64), o=k[:, 1].astype(np.float32), h=k[:, 2].astype(np.float32),
               l=k[:, 3].astype(np.float32), c=k[:, 4].astype(np.float32), qv=k[:, 6].astype(np.float32),
               tb=k[:, 8].astype(np.float32), n=k[:, 7].astype(np.float32))
    return s, arr, (np.array(sorted(set(fr))) if fr else None), info


def pad(K, g):
    """Как s117/load_oos.pad, но сетка g задана явно (сплошная, шаг 900 с): заглушки без объёма с последней ценой."""
    for s, a in list(K.items()):
        if len(a["t"]) == len(g) and (a["t"] == g).all():
            continue
        idx = np.searchsorted(g, a["t"])
        ok = (idx < len(g)) & (g[np.minimum(idx, len(g) - 1)] == a["t"])
        pos = np.full(len(g), -1)
        pos[idx[ok]] = np.flatnonzero(ok)
        filled = np.maximum.accumulate(np.where(pos >= 0, np.arange(len(g)), -1))
        first = np.flatnonzero(pos >= 0)[0]
        src = np.where(filled >= 0, pos[np.maximum(filled, 0)], pos[first])
        out = {}
        for col in ("o", "h", "l", "c"):
            cl = a["c"][src]
            out[col] = np.where(pos >= 0, a[col][np.maximum(pos, 0)], cl).astype(np.float32)
        for col in ("qv", "tb", "n"):
            out[col] = np.where(pos >= 0, a[col][np.maximum(pos, 0)], 0).astype(np.float32)
        out["t"] = g.copy()
        K[s] = out
    return K


def fill_funding(K, F):
    """Месяцы, где перп торговался ≥ 1 сут, а начислений в архиве < 90% от 3 в сутки, — дозаполнить с API."""
    done = []
    for s, a in K.items():
        q = a["qv"] > 0
        m = a["t"].astype("datetime64[s]").astype("datetime64[M]")
        f = F.get(s)
        fm = (f[:, 0].astype(np.int64).astype("datetime64[s]").astype("datetime64[M]") if f is not None
              else np.array([], "datetime64[M]"))
        for mm in np.unique(m[q]):
            n = int((q & (m == mm)).sum())
            if n < 96 or (fm == mm).sum() >= n / 32 * 0.9:
                continue
            t0 = int(mm.astype("datetime64[s]").astype(np.int64))
            t1 = int((mm + np.timedelta64(1, "M")).astype("datetime64[s]").astype(np.int64))
            af = cached(f"{s}_funding_{str(mm)}", lambda: api_funding(s, t0, t1))
            old = [tuple(x) for x in f.tolist()] if f is not None else []
            have = {int(x[0]) for x in old}
            add = [(float(t), 8.0, float(r)) for t, r in af if int(t) not in have]
            F[s] = np.array(sorted(old + add))
            done.append((s, str(mm), len(add)))
    return done


def check_overlap():
    """Сверка API с архивом на 01.01.2020 (BTC, ETH): наибольшее расхождение по колонкам."""
    for s in ("BTC", "ETH"):
        a = to_rows(api_klines(s, T_ARCH0, T_ARCH0 + 86400))
        b = bv.kfull(s, "klines", "15m", ["2020-01"])
        b = b[b[:, 0] < T_ARCH0 + 86400]
        if len(a) != len(b):
            log(f"сверка {s}: разное число свечей API {len(a)} / архив {len(b)}")
            continue
        d = np.abs(a - b).max(axis=0)
        log(f"сверка API и архива {s} 01.01.2020: свечей {len(a)}, наибольшее расхождение по колонкам "
            f"t o h l c v qv n tb = {np.round(d, 6).tolist()}")


def main():
    t_start = time.time()
    S = symbols()
    log("символов в архиве:", len(S))
    K, F, I = {}, {}, {}
    with ThreadPoolExecutor(8) as ex:
        for n, (s, a, f, info) in enumerate(ex.map(one, S)):
            if a is not None:
                K[s] = a
            if f is not None and a is not None:
                F[s] = f
            if info is not None:
                I[s] = info
            if n % 100 == 0:
                log(n, "из", len(S), "| в периоде", len(K))
    check_overlap()
    log("фандинг дозаполнен с API (монета, месяц, начислений):", fill_funding(K, F))
    t0 = int(K["BTC"]["t"][0])
    g = np.arange(t0, T_END, 900, dtype=np.int64)
    gaps = {s: int(len(g) - len(a["t"])) for s, a in K.items()}
    K = pad(K, g)
    pickle.dump(K, open(f"{OUT}/k_2019.pkl", "wb"), protocol=4)
    pickle.dump(F, open(f"{OUT}/fund_2019.pkl", "wb"), protocol=4)
    first = {}
    for s, a in K.items():
        nz = np.flatnonzero(a["qv"] > 0)
        first[s] = int(a["t"][nz[0]]) if len(nz) else None
    pickle.dump(dict(info=I, first=first), open(f"{OUT}/k_2019_meta.pkl", "wb"))
    api_syms = sorted(s for s, x in I.items() if x["api_k"])
    t0s = datetime.datetime.fromtimestamp(t0, datetime.timezone.utc).strftime("%d.%m.%Y %H:%M")
    api_txt = ", ".join(f"{s}: {I[s]['api_k']} свечей, {I[s]['api_f']} начислений (шаг {I[s].get('api_f_steps_h')} ч)"
                        for s in api_syms)
    log(f"монет {len(K)} | свечей на монету {len(g)} (с {t0s} по 30.09.2020 23:45) | с фандингом {len(F)}")
    log(f"09–12.2019 с API: {api_txt}")
    log("пропусков сетки у BTC до дополнения:", gaps.get("BTC"))
    # агрессивные покупки: доля живых свечей с tb = 0 по месяцам
    zt, tot, nsym = {}, {}, {}
    for s, a in K.items():
        live = a["qv"] > 0
        m = a["t"][live].astype("datetime64[s]").astype("datetime64[M]").astype(str)
        z = a["tb"][live] == 0
        for mm in np.unique(m):
            tot[mm] = tot.get(mm, 0) + int((m == mm).sum())
            zt[mm] = zt.get(mm, 0) + int(z[m == mm].sum())
            nsym[mm] = nsym.get(mm, 0) + 1
    log("перпов с торгами по месяцам: " + ", ".join(f"{m} {nsym[m]}" for m in sorted(nsym)))
    log("живых 15-мин свечей с tb = 0 по месяцам: " + ", ".join(f"{m} {zt[m]}/{tot[m]}" for m in sorted(tot)))
    log(f"готово за {time.time() - t_start:.0f} с")


if __name__ == "__main__":
    main()
