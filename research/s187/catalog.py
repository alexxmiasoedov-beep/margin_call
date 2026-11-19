"""s187 — каталог популярных скриптов TradingView за всё время.

Источник сортировки «за всё время» — поиск сообщества, которым пользуется окно «Индикаторы» графика:
`https://www.tradingview.com/pubscripts-suggest-json/?search=<префикс>&type=<1|2>&sort=top&offset=<n>`
(type 1 — индикаторы, 2 — стратегии, 3 — библиотеки; sort — top / recent / relevant; поиск — по началу слов
названия, пустой запрос ничего не отдаёт; страница — 50 записей, сортировка по `agreeCount` — числу бустов (лайков)
за всё время). Лента `/scripts/` сортирует только «популярные из свежих» (latest_popular) и «новые», до 1000 записей.

Шаги (каждый ответ кэшируется в /home/user/mc_data/s187/, повторный запуск сеть не трогает):
  python3 catalog.py search   — префиксы a–z, 0–9 по индикаторам и стратегиям, страницы до порога бустов;
  python3 catalog.py pages    — страницы скриптов топа (дата, бусты, просмотры, описание, таймфрейм публикации);
  python3 catalog.py source   — исходники открытых скриптов топа через pine-facade → /home/user/mc_data/s187/pine/;
  python3 catalog.py table    — сводная таблица → catalog.csv (метаданные, без исходников).

Запросы — не чаще одного в 3 с, User-Agent «research-script/1.0», при 429/403 и сетевых ошибках — растущая пауза.
Исходники Pine остаются только в папке данных (лицензии авторов, обычно MPL 2.0)."""
import csv
import glob
import json
import os
import re
import string
import sys
import time

import requests

D = "/home/user/mc_data/s187"
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "research-script/1.0"}
PAUSE = 3.0
PREFIXES = list(string.ascii_lowercase) + list(string.digits)
THRESH = {1: 9000, 2: 1500}          # страницы префикса листаются, пока последний скрипт страницы не ниже порога
TOP = {1: 100, 2: 40}                 # сколько брать в каталог
KIND = {1: "indicator", 2: "strategy"}
_last = [0.0]


def fetch(url, path, tries=5):
    """GET с кэшем на диске; None — 404/ошибка после повторов."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return open(path, encoding="utf-8").read()
    for k in range(tries):
        wait = PAUSE - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = requests.get(url, headers=UA, timeout=40)
        except requests.RequestException as e:
            print("  сеть:", type(e).__name__, url, flush=True)
            time.sleep(20 * (k + 1))
            continue
        if r.status_code in (403, 429, 503):
            print("  ответ", r.status_code, "— пауза", url, flush=True)
            time.sleep(60 * (k + 1))
            continue
        if r.status_code != 200:
            print("  ответ", r.status_code, url, flush=True)
            return None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(r.text)
        return r.text
    return None


def search():
    for typ in (1, 2):
        for q in PREFIXES:
            off = 0
            while True:
                url = f"https://www.tradingview.com/pubscripts-suggest-json/?search={q}&type={typ}&sort=top&offset={off}"
                txt = fetch(url, f"{D}/suggest/t{typ}_{q}_{off}.json")
                if txt is None:
                    break
                j = json.loads(txt)
                res = j.get("results") or []
                last = res[-1]["agreeCount"] if res else 0
                print(f"type {typ} «{q}» offset {off}: {len(res)} записей, последняя {last}", flush=True)
                if not res or not j.get("next") or last < THRESH[typ]:
                    break
                off += 50


# скрипты из списка задачи, которых может не быть в топе-100: поиск по названию (первая страница, сортировка top)
EXTRA_Q = ["QQE MOD", "Range Filter", "HalfTrend", "SSL Channel", "Nadaraya-Watson Rational Quadratic Kernel",
           "Ichimoku", "Stoch RSI", "Stochastic RSI", "VuManChu Cipher", "Lorentzian", "Hull Suite", "Chandelier Exit",
           "Williams Vix Fix", "WaveTrend", "MACD Divergence", "RSI Divergence", "Squeeze Momentum", "UT Bot",
           "Market Cipher", "LuxAlgo Signals", "AlgoAlpha", "Smart Money Concepts", "Range Filter Buy and Sell",
           "QQE", "SSL Hybrid", "Supertrend", "Heikin Ashi", "Bollinger Bands", "VWAP", "Volume Profile"]


def extra():
    for q in EXTRA_Q:
        url = "https://www.tradingview.com/pubscripts-suggest-json/?search=" + requests.utils.quote(q) + "&sort=top"
        txt = fetch(url, f"{D}/suggest/x_{re.sub(r'[^A-Za-z0-9]+', '_', q)}.json")
        res = (json.loads(txt).get("results") or []) if txt else []
        print(f"«{q}»:", "; ".join(f"{x['scriptName'][:50]} ({x['author']['username']}, {x['agreeCount']})"
                                    for x in res[:4]), flush=True)


def union():
    """Объединение ответов поиска: scriptIdPart → запись (без исходника), бусты — наибольшие из встреченных."""
    U = {}
    for f in glob.glob(f"{D}/suggest/t*_*.json"):
        typ = int(os.path.basename(f)[1])
        for x in json.load(open(f, encoding="utf-8")).get("results") or []:
            k = x["scriptIdPart"]
            rec = {kk: vv for kk, vv in x.items() if kk != "scriptSource"}
            rec["type_q"] = typ
            if k not in U or rec["agreeCount"] > U[k]["agreeCount"]:
                U[k] = rec
    return U


def top_lists():
    U = union()
    out = {}
    for typ in (1, 2):
        kind = "study" if typ == 1 else "strategy"
        xs = [x for x in U.values() if x["extra"].get("kind") == kind]
        xs.sort(key=lambda x: -x["agreeCount"])
        out[typ] = xs[:TOP[typ]]
    return out, U


def page_obj(html):
    """Объект идеи из встроенного init-data страницы скрипта."""
    for b in re.findall(r'<script type="application/prs.init-data\+json">(.*?)</script>', html, re.S):
        try:
            j = json.loads(b)
        except ValueError:
            continue
        st = [j]
        while st:
            o = st.pop()
            if isinstance(o, dict):
                if "likes_count" in o and "name" in o and "script" in o:
                    return o
                st.extend(o.values())
            elif isinstance(o, list):
                st.extend(o)
    return None


def pages():
    tops, _ = top_lists()
    for typ in (1, 2):
        for i, x in enumerate(tops[typ]):
            u = x["imageUrl"]
            txt = fetch(f"https://www.tradingview.com/script/{u}/", f"{D}/pages/{u}.html")
            if txt is None:
                print("  нет страницы", u, x["scriptName"], flush=True)
                continue
            o = page_obj(txt)
            meta = {}
            if o:
                sc = o.get("script") or {}
                meta = dict(uuid=o.get("uuid"), url="https://www.tradingview.com" + (o.get("chart_url") or ""),
                            created_at=o.get("created_at"), updated_at=o.get("updated_at"),
                            likes=o.get("likes_count"), views=o.get("views"), comments=o.get("comments_count"),
                            interval=o.get("interval"), description=o.get("description"),
                            tags=[t.get("tag") for t in o.get("tags") or []],
                            updates=[{"created": u2.get("created_at"), "text": (u2.get("description") or "")[:2000]}
                                     for u2 in o.get("updates") or []],
                            is_picked=(o.get("flags") or {}).get("is_picked"),
                            access=sc.get("access"), script_id_part=sc.get("script_id_part"),
                            user=(o.get("user") or {}).get("username"))
            json.dump(meta, open(f"{D}/pages/{u}.json", "w", encoding="utf-8"), ensure_ascii=False)
            os.remove(f"{D}/pages/{u}.html")                # страница большая (≈0,5 МБ) — храним только выжимку
            print(f"{KIND[typ]} {i + 1}: {x['scriptName']} — {meta.get('likes')} бустов, {meta.get('created_at')}",
                  flush=True)


def source():
    tops, _ = top_lists()
    for typ in (1, 2):
        for x in tops[typ]:
            if x["access"] != 1:
                continue
            pid = x["scriptIdPart"]
            txt = fetch(f"https://pine-facade.tradingview.com/pine-facade/get/{pid}/last?no_4xx=true",
                        f"{D}/pf/{pid.replace(';', '_')}.json")
            if txt is None:
                continue
            j = json.loads(txt)
            src = j.get("source")
            if not src:
                print("  без исходника:", x["scriptName"], j.get("reason"), flush=True)
                continue
            with open(f"{D}/pine/{x['imageUrl']}.pine", "w", encoding="utf-8") as f:
                f.write(src.replace("\r\n", "\n"))
            print("исходник:", x["scriptName"], len(src), j.get("scriptAccess"), flush=True)


ACCESS = {1: "открытый", 2: "защищённый", 3: "по приглашению"}


def pine_version(src):
    m = re.search(r"//\s*@version\s*=\s*(\d+)", src or "")
    return int(m.group(1)) if m else 1 if src else None


def table():
    tops, _ = top_lists()
    rows = []
    for typ in (1, 2):
        for rank, x in enumerate(tops[typ], 1):
            u = x["imageUrl"]
            mp = f"{D}/pages/{u}.json"
            meta = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
            sp = f"{D}/pine/{u}.pine"
            src = open(sp, encoding="utf-8").read() if os.path.exists(sp) else None
            rows.append(dict(
                kind=KIND[typ], rank=rank, name=x["scriptName"], author=x["author"]["username"],
                url=meta.get("url") or f"https://www.tradingview.com/script/{u}/",
                boosts=x["agreeCount"], views=meta.get("views"), comments=meta.get("comments"),
                access=ACCESS.get(x["access"], x["access"]), pine=pine_version(src), pub_version=x["version"],
                created=(meta.get("created_at") or "")[:10], interval=meta.get("interval"),
                editors_pick=meta.get("is_picked"), uuid=u, id=x["scriptIdPart"], src_lines=src.count("\n") + 1 if src else None))
    with open(os.path.join(HERE, "catalog.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "строк → catalog.csv")


if __name__ == "__main__":
    {"search": search, "extra": extra, "pages": pages, "source": source, "table": table}[sys.argv[1]]()
