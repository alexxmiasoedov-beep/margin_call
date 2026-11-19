"""s196 — выход из стейкинга Tezos и Aptos без ключа.
- Tezos (XTZ): TzKT api.tzkt.io/v1/staking/updates?type=unstake (с 02.2024, «staked» после Paris; делегирование в Tezos
  не блокирует монеты), сумма в mutez; finalize — когда монеты стали ликвидными.
- Aptos (APT): GraphQL api.mainnet.aptoslabs.com/v1/graphql, delegated_staking_activities, событие
  0x1::delegation_pool::UnlockStakeEvent (с 2023 г.), сумма в octa; монеты становятся ликвидными в конце цикла блокировки
  пула (до 14 сут, раньше до 30). Окна по номерам версий, фильтр суммы ≥ 10 000 APT; время версии — из
  block_metadata_transactions. Итог — /home/user/mc_data/s196/tezos_unstake.json, aptos_unlock.json."""
import json
import os
import sys
import time
from common196 import http, OUT

G = "https://api.mainnet.aptoslabs.com/v1/graphql"


def tezos():
    p = f"{OUT}/tezos_unstake.json"
    if os.path.exists(p):
        return json.load(open(p))
    out = {}
    for typ in ("unstake", "finalize"):
        rows, last = [], 0
        while True:
            d = http(f"https://api.tzkt.io/v1/staking/updates?type={typ}&id.gt={last}&sort.asc=id&limit=10000"
                     f"&select=id,timestamp,cycle,amount,staker.address,baker.address")
            if not d:
                break
            rows += d
            last = d[-1]["id"]
            if len(d) < 10000:
                break
        out[typ] = rows
        print("tezos", typ, len(rows), flush=True)
    json.dump(out, open(p, "w"))
    return out


def gql(q):
    return http(G, data={"query": q}, timeout=60, tries=4)


def aptos(min_octa=10_000 * 10 ** 8, step=100_000_000):
    """UnlockStakeEvent (события v1) и UnlockStake (модульные события v2, с ~2025 г.) — оба имени типа."""
    p = f"{OUT}/aptos_unlock.json"
    out = json.load(open(p)) if os.path.exists(p) else {"rows": [], "done": 0, "vt": {}}
    if not out.get("v2_done"):
        _aptos_pass(out, "0x1::delegation_pool::UnlockStake", min_octa, step, key="done_v2")
        out["v2_done"] = True
        json.dump(out, open(p, "w"))
    return _aptos_pass(out, "0x1::delegation_pool::UnlockStakeEvent", min_octa, step, key="done")


def _aptos_pass(out, etype, min_octa, step, key):
    p = f"{OUT}/aptos_unlock.json"
    head = gql("{ processor_status(where:{processor:{_eq:\"stake_processor\"}}) "
               "{ last_success_version } }")
    try:
        last = int(head["data"]["processor_status"][0]["last_success_version"])
    except Exception:
        last = 8_100_000_000
    v = out.get(key, 0)
    while v < last:
        w = min(v + step, last)
        q = ('{ delegated_staking_activities(limit:1000, where:{event_type:{_eq:"' + etype + '"}, '
             f'amount:{{_gte:"{min_octa}"}}, transaction_version:{{_gte:"{v}", _lt:"{w}"}}}}, order_by:{{transaction_version:asc}})'
             ' { amount delegator_address pool_address transaction_version } }')
        d = gql(q)
        if not d or "data" not in d:
            if step > 5_000_000:
                step //= 2
                continue
            print("aptos сбой", v, d, flush=True)
            break
        rows = d["data"]["delegated_staking_activities"]
        if len(rows) == 1000 and step > 1_000_000:
            step //= 2
            continue
        out["rows"] += [[int(r["transaction_version"]), int(r["amount"]) / 1e8, r["delegator_address"], r["pool_address"]]
                        for r in rows]
        v = w
        out[key] = v
        if v // step % 10 == 0:
            print("aptos версия", v, "событий", len(out["rows"]), flush=True)
            json.dump(out, open(p, "w"))
    # время версий: сетка block_metadata_transactions
    for g in range(0, last + 50_000_000, 50_000_000):
        if str(g) in out["vt"]:
            continue
        d = gql('{ block_metadata_transactions(limit:1, where:{version:{_gte:"%d"}}, order_by:{version:asc}) '
                '{ version timestamp } }' % g)
        try:
            b = d["data"]["block_metadata_transactions"][0]
            out["vt"][str(g)] = [int(b["version"]), b["timestamp"][:19]]
        except Exception:
            pass
    json.dump(out, open(p, "w"))
    print("aptos всего событий ≥ 10 тыс. APT:", len(out["rows"]), flush=True)
    return out


if __name__ == "__main__":
    w = sys.argv[1:] or ["tezos", "aptos"]
    if "tezos" in w:
        tezos()
    if "aptos" in w:
        aptos()
