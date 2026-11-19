"""s196 — очередь анбондинга сетей Cosmos SDK на прошлых высотах (архивные REST-узлы из cosmos/chain-registry, без ключа):
снимок = все unbonding_delegations валидаторов BONDED и UNBONDING на высоте H (заголовок x-cosmos-block-height).
Запись живёт от создания до завершения (21 сут), поэтому снимок покрывает все анбондинги, начатые за 21 сут до H,
с точной датой завершения (completion_time) и суммой. Снимки — несколько на период (выборка, без доходов).
Итог — /home/user/mc_data/s196/cosmos/<сеть>_<высота>.json."""
import calendar
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.parse
from common196 import http, OUT

CH = {
    "atom": dict(rest=["https://api.cosmoshub-4-archive.citizenweb3.com:443", "https://rest.cosmoshub-main.ccvalidators.com:443"],
                 exp=6, h0=5200791, dates=["2021-04-15", "2021-09-15", "2022-02-15", "2022-07-15",
                               "2022-12-15", "2023-05-15", "2023-10-15", "2024-03-15",
                               "2024-12-15", "2025-05-15", "2025-10-15", "2026-03-15", "2026-08-15", "2026-11-18"]),
    "tia": dict(rest=["https://public-celestia-lcd.numia.xyz", "https://api.archive.celestia.validatus.com"],
                exp=6, h0=1, dates=["2023-12-20", "2024-03-15", "2024-06-15", "2024-09-15",
                              "2024-12-15", "2025-05-15", "2025-10-15", "2026-03-15", "2026-08-15", "2026-11-18"]),
    "kava": dict(rest=["https://api.data.kava.io"],
                 exp=6, h0=1, dates=["2022-07-15", "2022-12-15", "2023-05-15", "2023-10-15", "2024-03-15",
                               "2024-12-15", "2025-05-15", "2025-10-15", "2026-03-15", "2026-08-15", "2026-11-18"]),
    "ntrn": dict(rest=["https://rest-archive.neutron.solva.solutions:443"], exp=6,
                 dates=["2025-08-15", "2026-01-15", "2026-06-15", "2026-11-18"]),
}


def get(ch, path, h, tries=4):
    for base in CH[ch]["rest"]:
        d = http(base + path, headers={"x-cosmos-block-height": str(h)} if h else None, timeout=120, tries=tries)
        if d is not None and "code" not in d:
            return d
    return None


def btime(ch, h):
    d = get(ch, f"/cosmos/base/tendermint/v1beta1/blocks/{h}", None, tries=3)
    try:
        t = d["block"]["header"]["time"][:19]
        return calendar.timegm(time.strptime(t, "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return None


def height_at(ch, target):
    """интерполяционный поиск высоты по времени заголовка."""
    d = get(ch, "/cosmos/base/tendermint/v1beta1/blocks/latest", None)
    hi = int(d["block"]["header"]["height"])
    thi = btime(ch, hi)
    lo = hi - 1
    tlo = btime(ch, lo)
    # шаг назад, пока не перейдём цель
    step = 200000
    h0 = CH[ch].get("h0", 1)
    while tlo is None or tlo > target:
        lo = max(h0, lo - step)
        tlo = btime(ch, lo)
        step *= 2
        if lo == h0:
            break
    for _ in range(40):
        if hi - lo <= 50:
            break
        if tlo is None or thi is None or thi == tlo:
            mid = (lo + hi) // 2
        else:
            mid = int(lo + (hi - lo) * (target - tlo) / (thi - tlo))
            mid = min(max(mid, lo + 1), hi - 1)
        tm = btime(ch, mid)
        if tm is None:
            mid = (lo + hi) // 2
            tm = btime(ch, mid)
            if tm is None:
                break
        if tm < target:
            lo, tlo = mid, tm
        else:
            hi, thi = mid, tm
    return hi, thi


def vals(ch, h):
    out = []
    for st in ("BOND_STATUS_BONDED", "BOND_STATUS_UNBONDING"):
        key = ""
        while True:
            d = get(ch, f"/cosmos/staking/v1beta1/validators?status={st}&pagination.limit=500" +
                    (f"&pagination.key={urllib.parse.quote(key)}" if key else ""), h)
            if not d:
                break
            out += [(v["operator_address"], int(v["tokens"])) for v in d.get("validators") or []]
            key = (d.get("pagination") or {}).get("next_key") or ""
            if not key:
                break
    return out


def unb(ch, h, v):
    rows, key = [], ""
    while True:
        d = get(ch, f"/cosmos/staking/v1beta1/validators/{v}/unbonding_delegations?pagination.limit=1000" +
                (f"&pagination.key={urllib.parse.quote(key)}" if key else ""), h)
        if d is None:
            return rows, False
        for u in d.get("unbonding_responses") or []:
            for e in u.get("entries") or []:
                rows.append([u["delegator_address"], v, int(e["creation_height"]), e["completion_time"][:19],
                             int(e["initial_balance"]), int(e["balance"])])
        key = (d.get("pagination") or {}).get("next_key") or ""
        if not key:
            return rows, True


def snap(ch, date):
    os.makedirs(f"{OUT}/cosmos", exist_ok=True)
    target = calendar.timegm(time.strptime(date, "%Y-%m-%d")) + 12 * 3600
    p = f"{OUT}/cosmos/{ch}_{date}.json"
    if os.path.exists(p):
        return json.load(open(p))
    h, t = height_at(ch, target)
    V = vals(ch, h)
    rows, bad = [], 0
    with cf.ThreadPoolExecutor(4) as ex:
        for r, ok in ex.map(lambda v: unb(ch, h, v[0]), V):
            rows += r
            bad += (not ok)
    exp = CH[ch]["exp"]
    res = {"chain": ch, "date": date, "height": h, "time": t, "n_val": len(V), "bad_val": bad,
           "bonded": sum(x[1] for x in V) / 10 ** exp, "rows": rows}
    json.dump(res, open(p, "w"))
    print(f"{ch} {date} высота {h} валидаторов {len(V)} (сбоев {bad}) записей {len(rows)} "
          f"в очереди {sum(r[5] for r in rows) / 10 ** exp:,.0f}", flush=True)
    return res


if __name__ == "__main__":
    chains = sys.argv[1:] or list(CH)
    for ch in chains:
        for d in CH[ch]["dates"]:
            try:
                snap(ch, d)
            except Exception as e:
                print(ch, d, "ошибка", repr(e)[:200], flush=True)
