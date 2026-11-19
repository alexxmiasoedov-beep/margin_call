"""s196 — ставки с заранее известным концом: Avalanche (P-chain, срок ставки валидатора и делегатора задаётся при
создании, монеты возвращаются в конце автоматически) и Internet Computer (нейрон в состоянии Dissolving становится
ликвидным через dissolve_delay; «сейчас» — календарь вперёд).
- AVAX: Glacier API (glacier-api.avax.network, без ключа): /v1/networks/mainnet/validators?validationStatus=completed|active
  (amountStaked, startTimestamp, endTimestamp, с 09.2020); делегаторы ≥ 50 тыс. AVAX — выборка.
- ICP: ic-api.internetcomputer.org/api/v3/neurons (список нейронов по размеру, state, dissolve_delay_seconds).
Итог — /home/user/mc_data/s196/avax_validators.json, icp_neurons.json."""
import json
import os
import sys
import time
from common196 import http, OUT

GL = "https://glacier-api.avax.network/v1/networks/mainnet"


def avax(pages=100):
    """выборка валидаций Glacier: самые новые (по убыванию конца) и самые старые (asc) — по pages страниц по 100."""
    p = f"{OUT}/avax_validators.json"
    if os.path.exists(p):
        return json.load(open(p))
    out = {}
    for st, order in (("completed", "desc"), ("completed", "asc")):
        rows, tok, k = [], None, 0
        while k < pages:
            u = (f"{GL}/validators?pageSize=100&validationStatus={st}&sortOrder={order}"
                 f"&subnetId=11111111111111111111111111111111LpoYY")
            if tok:
                u += f"&pageToken={tok}"
            d = http(u, timeout=90)
            if not d:
                break
            for v in d.get("validators") or []:
                rows.append([v.get("txHash"), v.get("nodeId"), int(v.get("amountStaked") or 0) / 1e9,
                             int(v.get("amountDelegated") or 0) / 1e9, v.get("startTimestamp"), v.get("endTimestamp"),
                             (v.get("rewards") or {}).get("rewardAddresses")])
            tok = d.get("nextPageToken")
            k += 1
            if not tok:
                break
            time.sleep(0.15)
        out[f"{st}_{order}"] = rows
        print("avax", st, order, "валидаций", len(rows), flush=True)
    json.dump(out, open(p, "w"))
    return out


def icp(n_pages=40):
    p = f"{OUT}/icp_neurons.json"
    if os.path.exists(p):
        return json.load(open(p))
    rows = []
    for k in range(n_pages):
        d = http(f"https://ic-api.internetcomputer.org/api/v3/neurons?limit=100&offset={100 * k}&sort_by=-stake_e8s",
                 timeout=90)
        if not d:
            break
        for x in d.get("data") or []:
            rows.append([x["id"], x["stake_e8s"] / 1e8, x["state"], x["dissolve_delay_seconds"],
                         x.get("created_timestamp_seconds"), x.get("retrieved_at_timestamp_seconds"), x.get("is_known")])
        time.sleep(0.2)
    json.dump(rows, open(p, "w"))
    print("icp нейронов", len(rows), "наименьший", rows[-1][1] if rows else None, flush=True)
    return rows


if __name__ == "__main__":
    w = sys.argv[1:] or ["avax", "icp"]
    if "icp" in w:
        icp()
    if "avax" in w:
        avax()
