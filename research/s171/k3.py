"""s171 — К3: займ за 24 ч к капитализации монеты (гипотеза — ВЫВОДЫ.md, записана до расчёта). Капитализация — CMC data-api
`cryptocurrency/historical` (монеты в обращении × цена закрытия), на последний день не позже суток до T. Монета CMC —
среди монет с тем же тикером (map/all, все статусы, `s167/cmc_map_all.json`) та, у которой медиана отношения цены CMC
к цене фьючерса (с множителем 1000…) 0,8–1,25 и ближе к 1. Кэш — s171/cmc/<id>.json. Дописывает в s171_events.pkl
столбцы mcap и bmc (займ / капитализация) и печатает итог К3. Запуск из /home/user/mc_data:
python3 <repo>/research/s171/k3.py"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
sys.path.insert(0, HERE)
API = "https://api.coinmarketcap.com/data-api/v3"
UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}
EDGES = [int(pd.Timestamp(d, tz="UTC").timestamp()) for d in ("2025-01-15", "2025-12-31", "2026-11-01")]


def get(url):
    for i in range(6):
        try:
            out = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(0.4)
            return out
        except urllib.error.HTTPError as e:
            time.sleep(60 if e.code == 429 else 4 + 4 * i)
        except Exception:
            time.sleep(4 + 4 * i)
    return None


def hist(cid):
    path = f"s171/cmc/{cid}.json"
    if os.path.exists(path):
        return json.load(open(path))
    out = []
    for t0, t1 in zip(EDGES[:-1], EDGES[1:]):
        d = get(f"{API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={t0}&timeEnd={t1}&interval=1d")
        for q in ((d or {}).get("data") or {}).get("quotes") or []:
            u = q["quote"]
            out.append([q["timeClose"][:10], u.get("circulatingSupply"), u.get("close"), u.get("marketCap")])
    json.dump(out, open(path, "w"))
    return out


def base(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    if m and not m.group(2)[0].isdigit():
        return m.group(2), 1e6 if m.group(1) in ("1M", "1000000") else float(m.group(1))
    return fs, 1.0


def main():
    from common import K  # noqa: E402
    os.makedirs("s171/cmc", exist_ok=True)
    E = pd.read_pickle("s171_events.pkl")
    cmc = json.load(open("s167/cmc_map_all.json"))
    by = {}
    for c in cmc:
        by.setdefault(str(c.get("symbol") or "").upper(), []).append(c)
    pick = {}
    for fs in sorted(E.s.unique()):
        coin, mult = base(fs)
        if fs not in K:
            continue
        a = K[fs]; m = (a["qv"] > 0) & (a["t"] % 86400 == 86400 - 900)
        px = pd.Series(a["c"][m].astype(float) / mult, index=pd.to_datetime(a["t"][m].astype(np.int64) // 86400 * 86400, unit="s").strftime("%Y-%m-%d"))
        best = None
        for c in by.get(coin, []):
            h = hist(c["id"])
            q = pd.Series({d: cl for d, _, cl, _ in h if cl}, dtype=float)
            j = q.index.intersection(px.index)
            if len(j) < 20:
                continue
            r = float(np.median(q[j].values / px[j].values))
            if 0.8 <= r <= 1.25 and (best is None or abs(np.log(r)) < abs(np.log(best[1]))):
                best = (c["id"], r)
        if best:
            pick[fs] = best[0]
    print("монет с капитализацией CMC:", len(pick), "из", E.s.nunique(), flush=True)
    mc = []
    for r in E.itertuples():
        cid = pick.get(r.s)
        if cid is None:
            mc.append(np.nan); continue
        h = [x for x in json.load(open(f"s171/cmc/{cid}.json")) if x[1] and x[2]]
        day = pd.Timestamp(int(r.T) - 86400, unit="s").strftime("%Y-%m-%d")
        v = [x[1] * x[2] for x in h if x[0] <= day]
        mc.append(v[-1] if v else np.nan)
    E["mcap"] = mc; E["bmc"] = E.bor / E.mcap
    E.to_pickle("s171_events.pkl")
    print("событий с капитализацией:", int(E.mcap.notna().sum()), "из", len(E), "| займ / капитализация: медиана",
          f"{E.bmc.median():.4%}, доля ≥ 0,5%: {(E.bmc >= 0.005).mean():.1%}", flush=True)


if __name__ == "__main__":
    main()
