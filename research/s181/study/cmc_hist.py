"""s181 — монеты в обращении и оборот по дням из CMC data-api без ключа (`cryptocurrency/historical`), с 01.09.2020.
Кэш — /home/user/mc_data/s181/circ/<id>.json: [[дата, обращение, оборот за сутки $, закрытие $]].
Цена нужна только для перевода единиц в $ в день события (размер к обороту); доходы не считаются."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

API = "https://api.coinmarketcap.com/data-api/v3"
CIRC = f"{C.OUT}/circ"
os.makedirs(CIRC, exist_ok=True)


def hist(cid, end=1795100000):
    path = f"{CIRC}/{cid}.json"
    if os.path.exists(path):
        return json.load(open(path))
    out = []
    edges = [1598918400 + k * 31_536_000 for k in range(8)]
    for t0, t1 in zip(edges[:-1], edges[1:]):
        code, raw = C.get(f"{API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={t0}&timeEnd={min(t1, end)}"
                          f"&interval=1d", headers={"Accept": "application/json"})
        if code == 200 and raw:
            for q in ((json.loads(raw).get("data") or {}).get("quotes") or []):
                u = q["quote"]
                out.append([q["timeClose"][:10], u.get("circulatingSupply"), u.get("volume"), u.get("close")])
        time.sleep(0.6)
        if t1 > end:
            break
    json.dump(out, open(path, "w"))
    return out


def cmc_map():
    """Тикер → [(ранг, id, имя)] по списку CMC (кэш s167)."""
    L = json.load(open(f"{C.D}/s167/cmc_map_all.json"))
    by = {}
    for x in L:
        by.setdefault(str(x["symbol"]).upper(), []).append((x.get("rank") or 10 ** 9, x["id"], x["name"]))
    for k in by:
        by[k].sort()
    return by
