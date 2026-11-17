"""s111 — данные: дневные комиссии (fees) и выручка (revenue) протоколов DefiLlama для токенов с фьючерсом Binance
(без ключа). Список протоколов — /protocols (symbol, slug, parentProtocol);
токен сопоставляется с фьючерсом из s2/k2y.pkl по тикеру (с поправкой 1000x), у версий одного протокола берётся
родитель (parentProtocol): его ряд уже суммирует версии. История — /summary/fees/<slug>?dataType=dailyFees|dailyRevenue. Кэш — s111/llama/.
Запуск из папки с данными: python3 <repo>/research/s111/llama_fetch.py"""
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
from common import K  # noqa: E402

API = "https://api.llama.fi"


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(2 + 2 * k)
    return None


def main():
    os.makedirs("s111/llama", exist_ok=True)
    prots = get(f"{API}/protocols") or []
    base = {re.sub(r"^(1000000|100000|10000|1000)", "", s): s for s in K}
    keep = {}
    for p in prots:
        sym = str(p.get("symbol") or "").upper()
        if sym not in base:
            continue
        par = str(p.get("parentProtocol") or "")
        slug = par.split("#", 1)[1] if par.startswith("parent#") else p.get("slug")
        if slug:
            keep.setdefault(base[sym], set()).add(slug)
    keep = {s: sorted(v) for s, v in keep.items()}
    json.dump(keep, open("s111/map.json", "w"), indent=1)
    print(f"протоколов DefiLlama: {len(prots)}; токенов с фьючерсом Binance: {len(keep)}", flush=True)
    ov = get(f"{API}/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyFees")
    has = set()
    for q in (ov or {}).get("protocols", []):                    # у кого есть адаптер комиссий: сам протокол и его родитель
        has.add(q.get("slug"))
        par = str(q.get("parentProtocol") or "")
        if par.startswith("parent#"):
            has.add(par.split("#", 1)[1])
    keep = {s: [x for x in v if x in has] for s, v in keep.items()}
    keep = {s: v for s, v in keep.items() if v}
    json.dump(keep, open("s111/map.json", "w"), indent=1)
    print(f"с адаптером комиссий: токенов {len(keep)}, рядов {sum(len(v) for v in keep.values())}", flush=True)
    jobs = [(slug, dt) for slugs in keep.values() for slug in slugs for dt in ("dailyFees", "dailyRevenue")]
    jobs = sorted(set(j for j in jobs if not os.path.exists(f"s111/llama/{j[0]}_{j[1]}.json")))

    def one(job):
        slug, dt = job
        d = get(f"{API}/summary/fees/{slug}?dataType={dt}&excludeTotalDataChartBreakdown=true")
        if d is None:
            return 0                                             # сбой — не кэшируем, повторный запуск докачает
        json.dump(d.get("totalDataChart") or [], open(f"s111/llama/{slug}_{dt}.json", "w"))
        return 1

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as ex:
        n = sum(ex.map(one, jobs))
    print(f"скачано рядов: {n}", flush=True)


if __name__ == "__main__":
    main()
