"""Полная история CMC монеты для периода с 01.10.2024. Кэш s171/cmc (k3.hist) начинается только с 15.01.2025, поэтому
s220 (Solana), s243 (Base), s244 (Arbitrum) и первая версия s249 теряли события 01.10.2024–14.01.2025: доля завода
считалась от NaN. early() дозагружает 15.08.2024–15.01.2025 (кэш s249/cmc_early/<id>.json), full() склеивает.
Как скрипт — дописывает раннюю историю в готовые файлы монет в обращении (выбор монеты CMC не меняется):
python3 <repo>/research/s249/cmcfull.py s220/sol_circ.json s243/base_circ.json … (запуск из /home/user/mc_data)"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s171"))
import k3  # noqa: E402  (get(), API)

T0, T1 = "2024-08-15", "2025-01-15"


def early(cid):
    path = f"s249/cmc_early/{cid}.json"
    if os.path.exists(path):
        return json.load(open(path))
    a, b = (int(pd.Timestamp(d, tz="UTC").timestamp()) for d in (T0, T1))
    d = k3.get(f"{k3.API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={a}&timeEnd={b}&interval=1d")
    out = [[q["timeClose"][:10], q["quote"].get("circulatingSupply"), q["quote"].get("close"), q["quote"].get("marketCap")]
           for q in ((d or {}).get("data") or {}).get("quotes") or []]
    if d is not None:
        os.makedirs("s249/cmc_early", exist_ok=True)
        json.dump(out, open(path, "w"))
    return out


def full(cid, late):
    """Ранняя и поздняя история одной монеты CMC по дням без повторов (на стыке — поздняя)."""
    by = {r[0]: r for r in early(cid)}
    by.update({r[0]: r for r in late})
    return [by[d] for d in sorted(by)]


def patch(path):
    C = json.load(open(path))
    n0 = n1 = 0
    for fs, r in C.items():
        late = [[d, ci, cl, None] for d, ci, cl in r["days"]]
        days = [[d, ci, cl] for d, ci, cl, _ in full(r["cmc"], late) if ci and cl]
        n0 += len(r["days"]); n1 += len(days)
        r["days"] = days
    json.dump(C, open(path, "w"))
    first = sorted(min(d for d, _, _ in r["days"]) for r in C.values() if r["days"])
    print(f"{path}: монет {len(C)}, дней {n0} → {n1}; первый день — медиана {first[len(first) // 2]}", flush=True)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
