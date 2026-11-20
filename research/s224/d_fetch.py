"""s224b — сбор свежего отрезка D (метод — ВЫВОДЫ.md, коммит a47b59b) из тех же источников, что s216. Этапы:
- klines — 15-мин свечи перпов после конца s2/k2y.pkl (с 19.10.2026) по END: все символы архива, торговавшиеся до его конца,
  и новые перпы из exchangeInfo (www.binance.com/fapi/v1/klines: fapi.binance.com из облака отвечает 451) → s224/kl/<фьючерс>.npy;
- funding — фандинг с 30.09.2026 (www.binance.com/fapi/v1/fundingRate) → s224/fund/<фьючерс>.csv;
- posts — посты канала после s41/posts.jsonl (t.me/s, как s41/chng_scrape.py) → s224/posts_new.jsonl;
- rates — ставки займа после последней записи s11/rates (bapi сайта, как s11/rates_fetch.py) → s224/work/s11/rates;
- metrics — метрики позиций за сутки наблюдений D (data.binance.vision, как s216/fetch_metrics.py) → s224/work/s22/metrics_full;
- cmc — истории CMC с 01.11.2026 (data-api, как s171/k3.py) → s224/work/s171/cmc.
metrics и cmc идут после сборки панели (d_build.py panel). Исходные файлы в /home/user/mc_data не меняются.
Запуск из /home/user/mc_data: python3 <repo>/research/s224/d_fetch.py <этап> […]"""
import datetime
import glob
import json
import os
import pickle
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "research-script/1.0"}
WEB = "https://www.binance.com"
UTC = datetime.timezone.utc
KEND = 1792367100                                         # последняя свеча s2/k2y.pkl: 18.10.2026 23:45
TAIL0 = KEND + 900
END = int(datetime.datetime(2026, 11, 20, tzinfo=UTC).timestamp())   # исключительно: последние полные сутки — 19.11
OUT = "s224"
WORK = f"{OUT}/work"
_lock = threading.Lock()
_next = [0.0]
RATE = 2.5                                                # запросов в секунду к www.binance.com


def _wait():
    with _lock:
        now = time.time(); t = max(now, _next[0]); _next[0] = t + 1.0 / RATE
    if t > now:
        time.sleep(t - now)


def web(path):
    """GET к www.binance.com с паузами: 418/429 — минута и больше, прочие сбои — нарастающая пауза."""
    for i in range(6):
        _wait()
        try:
            url = WEB + urllib.parse.quote(path, safe="/?&=:%")      # фьючерсы с иероглифами (币安人生) — %-кодировка
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (418, 429):
                time.sleep(60 * (i + 1)); continue
            if e.code == 400:
                return None                               # символа нет (делистинг)
            time.sleep(3 * (i + 1))
        except Exception:
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"нет ответа: {path}")


def symbols():
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    ex = web("/fapi/v1/exchangeInfo")
    cur = {}
    for x in ex["symbols"]:
        if x.get("quoteAsset") == "USDT" and x["symbol"].endswith("USDT") and "PERPETUAL" in x.get("contractType", ""):
            cur[x["symbol"][:-4]] = int(x.get("onboardDate", 0)) // 1000
    old = [s for s in K if int(K[s]["t"][-1]) == KEND]
    new = [s for s in cur if s not in K and cur[s] < END]
    return K, cur, old, new


def klines():
    os.makedirs(f"{OUT}/kl", exist_ok=True)
    K, cur, old, new = symbols()
    print(f"символов архива до конца: {len(old)}, новых перпов: {len(new)}", flush=True)
    jobs = [(s, TAIL0) for s in old] + [(s, max(TAIL0, cur[s] // 900 * 900)) for s in new]

    def one(job):
        s, t0 = job
        path = f"{OUT}/kl/{s}.npy"
        if os.path.exists(path):
            return s, -1
        rows, st = [], t0
        while st < END:
            try:
                r = web(f"/fapi/v1/klines?symbol={s}USDT&interval=15m&startTime={st * 1000}&endTime={(END - 1) * 1000}&limit=1500")
            except RuntimeError as e:
                print("  сбой:", s, e, flush=True); return s, None       # файл не пишем — повтор при следующем запуске
            if not r:
                break
            rows += [[k[0] // 1000, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[7]), float(k[10]),
                      float(k[8])] for k in r]
            nxt = r[-1][0] // 1000 + 900
            if len(r) < 1500 or nxt <= st:
                break
            st = nxt
        a = np.array([x for x in rows if x[0] < END], dtype=np.float64).reshape(-1, 8)
        np.save(path, a)
        return s, len(a)
    t0, done = time.time(), 0
    with ThreadPoolExecutor(3) as ex:
        for s, n in ex.map(one, jobs):
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)} за {time.time() - t0:.0f} с", flush=True)
    print("свечи готовы", flush=True)


def funding():
    os.makedirs(f"{OUT}/fund", exist_ok=True)
    syms = sorted(os.path.basename(p)[:-4] for p in glob.glob(f"{OUT}/kl/*.npy"))
    f0 = int(datetime.datetime(2026, 9, 30, tzinfo=UTC).timestamp())

    def one(s):
        path = f"{OUT}/fund/{s}.csv"
        if os.path.exists(path):
            return
        rows, st = [], f0
        while st < END:
            try:
                r = web(f"/fapi/v1/fundingRate?symbol={s}USDT&startTime={st * 1000}&endTime={(END - 1) * 1000}&limit=1000")
            except RuntimeError as e:
                print("  сбой:", s, e, flush=True); return
            if not r:
                break
            rows += [(int(x["fundingTime"]), x["fundingRate"]) for x in r]
            if len(r) < 1000:
                break
            st = r[-1]["fundingTime"] // 1000 + 1
        with open(path, "w") as f:
            for t, v in rows:
                f.write(f"{t},{v}\n")
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(one, syms))
    print("фандинг готов:", len(syms), flush=True)


def posts():
    sys.path.insert(0, os.path.join(HERE, "..", "s41"))
    from chng_scrape import page  # noqa: E402
    last = 0
    for ln in open("s41/posts.jsonl"):
        last = max(last, json.loads(ln)[0])
    first = page()
    hi = max(p[0] for p in first) + 1
    seen = {p[0]: p for p in first if p[0] > last}
    befores = list(range(hi, last, -20))
    with ThreadPoolExecutor(2) as ex:
        for pp in ex.map(page, befores):
            for p in pp:
                if p[0] > last:
                    seen[p[0]] = p
    with open(f"{OUT}/posts_new.jsonl", "w") as f:
        for n in sorted(seen):
            f.write(json.dumps(seen[n], ensure_ascii=False) + "\n")
    miss = sorted(set(range(last + 1, hi)) - set(seen))
    print(f"постов после №{last}: {len(seen)} (№{min(seen)}…{max(seen)}), пропусков номеров {len(miss)}", flush=True)


def coins_after(t0):
    """Монеты канала с постами после t0 (старый разбор s7 и новые посты, разобранные d_build.gmerge)."""
    G = pickle.load(open(f"{WORK}/s7/margin.pkl", "rb"))["G"]
    return sorted(c for c, g in G.items() if len(g) and g[-1, 0] >= t0)


def panel_hours(base="."):
    """(фьючерс, час) наблюдений с 30.09.2026: из новой панели, если она уже собрана; иначе — с запасом из разбора канала
    (часы постов и следующий час; фьючерс — как s15/common.fut_of по символам архива и новым перпам)."""
    t0 = datetime.datetime(2026, 9, 30, tzinfo=UTC).timestamp()
    if os.path.exists(f"{base}/s21/panel.pkl"):
        D = pd.read_pickle(f"{base}/s21/panel.pkl")
        D = D[D["T"] >= t0]
        return list(zip(D.s, D["T"]))
    root = "/home/user/mc_data"
    names = set(pickle.load(open(f"{root}/s2/k2y.pkl", "rb"))) | {p[:-4] for p in os.listdir(f"{root}/{OUT}/kl")}
    G = pickle.load(open(f"{root}/{WORK}/s7/margin.pkl", "rb"))["G"]
    out = set()
    for c, g in G.items():
        s = next((p + c for p in ("", "1000", "1000000") if p + c in names), None)
        if s is None:
            continue
        for t in g[g[:, 0] >= t0 - 3600, 0]:
            h = int(t) // 3600 * 3600
            out.update(((s, h + 3600), (s, h + 7200)))
    return sorted(out)


def rates():
    B = "/bapi/margin/v1/public/margin/vip/spec/history-interest-rate"
    os.makedirs(f"{WORK}/s11/rates", exist_ok=True)
    for p in glob.glob("s11/rates/*.csv"):                    # всё неизменное — ссылки на исходные файлы
        q = f"{WORK}/s11/rates/{os.path.basename(p)}"
        if not os.path.lexists(q):
            os.symlink(os.path.abspath(p), q)
    strip = lambda s: re.sub(r"^(1000000|100000|10000|1000|1M)", "", s)
    need = sorted({strip(c) for c in coins_after(datetime.datetime(2026, 9, 1, tzinfo=UTC).timestamp())})
    now = time.time(); upd = new = 0
    for c in need:
        src = f"s11/rates/{c}.csv"; dst = f"{WORK}/s11/rates/{c}.csv"
        old = open(src).read().splitlines() if os.path.exists(src) else []
        if os.path.exists(src) and not old:
            continue                                          # у актива нет истории маржи (как в исходном сборе)
        last = int(old[-1].split(",")[0]) if old else int(datetime.datetime(2026, 8, 1, tzinfo=UTC).timestamp())
        res = {}
        a = last + 1
        while a < now:
            b = min(now, a + 31 * 86400 - 1)
            r = web(f"{B}?asset={c}&vipLevel=0&startTime={int(a * 1000)}&endTime={int(b * 1000)}")
            if r and r.get("success") and isinstance(r.get("data"), list):
                res.update({int(x["timestamp"]) // 1000: float(x["dailyInterestRate"]) for x in r["data"]})
            a = b + 1
        if os.path.lexists(dst):
            os.remove(dst)
        with open(dst, "w") as f:
            for ln in old:
                f.write(ln + "\n")
            for t in sorted(res):
                if t > last:
                    f.write(f"{t},{res[t]}\n")
        upd += bool(old); new += not old
    print(f"ставки: монет {len(need)}, дописано {upd}, новых файлов {new}", flush=True)


def metrics():
    sys.path.insert(0, os.path.join(HERE, "..", "s22"))
    from h12_fetch import full_day  # noqa: E402  (загружает s2/k2y.pkl из папки данных — до смены папки)
    hours = panel_hours(WORK)
    os.chdir(WORK)                                             # full_day пишет в s22/metrics_full относительно папки
    days = set()
    for s, T in hours:
        for dt in (0, -86400, -86400 - 4 * 3600, -3600, -86400 - 3600, -86400 - 5 * 3600):
            days.add((s, pd.Timestamp(T + dt, unit="s").strftime("%Y-%m-%d")))
    src = "/home/user/mc_data/s22/metrics_full"
    for s in {x[0] for x in days}:                             # неизменное — ссылки на исходные файлы
        os.makedirs(f"s22/metrics_full/{s}", exist_ok=True)
        for p in glob.glob(f"{src}/{s}/*.npy"):
            q = f"s22/metrics_full/{s}/{os.path.basename(p)}"
            if not os.path.lexists(q):
                os.symlink(p, q)
    need = sorted(x for x in days if not os.path.exists(f"s22/metrics_full/{x[0]}/{x[1]}.npy"))
    print("монето-суток", len(days), "докачать", len(need), flush=True)
    t0, done = time.time(), 0
    with ThreadPoolExecutor(8) as ex:
        for _ in ex.map(lambda x: full_day(*x), need):
            done += 1
            if done % 1000 == 0:
                print(f"  {done}/{len(need)} за {time.time() - t0:.0f} с", flush=True)
    print("метрики готовы", flush=True)


def cmc():
    sys.path.insert(0, os.path.join(HERE, "..", "s171"))
    import k3  # noqa: E402
    os.makedirs(f"{WORK}/s171/cmc", exist_ok=True)
    for p in glob.glob("s171/cmc/*.json"):
        q = f"{WORK}/s171/cmc/{os.path.basename(p)}"
        if not os.path.lexists(q):
            os.symlink(os.path.abspath(p), q)
    perps = sorted({s for s, _ in panel_hours(WORK)})
    by = {}
    for c in json.load(open("s167/cmc_map_all.json")):
        by.setdefault(str(c.get("symbol") or "").upper(), []).append(c)
    ids = sorted({c["id"] for fs in perps for c in by.get(k3.base(fs)[0], [])})
    t1 = int(datetime.datetime(2026, 11, 1, tzinfo=UTC).timestamp())
    upd = 0
    for cid in ids:
        dst = f"{WORK}/s171/cmc/{cid}.json"
        old = json.load(open(dst)) if os.path.exists(dst) else None
        if old is None:                                        # кэша не было — вся история, как k3.hist, плюс хвост
            old = []
            for a, b in zip(k3.EDGES[:-1], k3.EDGES[1:]):
                d = k3.get(f"{k3.API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={a}&timeEnd={b}&interval=1d")
                for q in ((d or {}).get("data") or {}).get("quotes") or []:
                    u = q["quote"]; old.append([q["timeClose"][:10], u.get("circulatingSupply"), u.get("close"), u.get("marketCap")])
        d = k3.get(f"{k3.API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={t1}&timeEnd={END}&interval=1d")
        new = [[q["timeClose"][:10], q["quote"].get("circulatingSupply"), q["quote"].get("close"), q["quote"].get("marketCap")]
               for q in ((d or {}).get("data") or {}).get("quotes") or []]
        have = {r[0] for r in old}
        rows = old + [r for r in new if r[0] not in have]
        if os.path.lexists(dst):
            os.remove(dst)
        json.dump(rows, open(dst, "w"))
        upd += 1
    print(f"CMC: монет CMC {len(ids)}, обновлено {upd}", flush=True)


if __name__ == "__main__":
    for st in sys.argv[1:]:
        {"klines": klines, "funding": funding, "posts": posts, "rates": rates, "metrics": metrics, "cmc": cmc}[st]()
