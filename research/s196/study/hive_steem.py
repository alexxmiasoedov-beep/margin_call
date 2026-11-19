"""s196 — «power down» Hive и Steem (вывод из Hive Power / Steem Power равными недельными частями: Hive — 13 недель,
Steem — 4 недели): график выплат записан в аккаунте (next_vesting_withdrawal, vesting_withdraw_rate, to_withdraw,
withdrawn). Снимок «сейчас» через публичные узлы без ключа (database_api.list_accounts по next_vesting_withdrawal).
История есть только как операции аккаунтов (withdraw_vesting) — без поиска по всей сети. Без доходов."""
import json
import time
from common196 import http, OUT
from freq_lib import Circ

NODES = {"hive": "https://api.hive.blog", "steem": "https://api.steemit.com"}


def snap(net):
    url = NODES[net]
    g = http(url, data={"jsonrpc": "2.0", "method": "condenser_api.get_dynamic_global_properties", "params": [], "id": 1})["result"]
    fund = float(str(g["total_vesting_fund_hive" if net == "hive" else "total_vesting_fund_steem"]).split()[0])
    shares = float(str(g["total_vesting_shares"]).split()[0])
    per_vest = fund / shares
    rows, start = [], ["1970-01-01T00:00:00", ""]
    while True:
        d = http(url, data={"jsonrpc": "2.0", "method": "database_api.list_accounts",
                            "params": {"start": start, "limit": 1000, "order": "by_next_vesting_withdrawal"}, "id": 1},
                 timeout=120)
        acc = ((d or {}).get("result") or {}).get("accounts") or []
        new = [a for a in acc if [a["next_vesting_withdrawal"], a["name"]] != start]
        if not new:
            break
        for a in new:
            if a["next_vesting_withdrawal"].startswith("1969") or a["next_vesting_withdrawal"].startswith("2106"):
                continue
            rate = int(a["vesting_withdraw_rate"]["amount"]) / 1e6 if isinstance(a["vesting_withdraw_rate"], dict) else \
                float(str(a["vesting_withdraw_rate"]).split()[0])
            tw, wd = int(a["to_withdraw"]) / 1e6, int(a["withdrawn"]) / 1e6
            rows.append([a["name"], a["next_vesting_withdrawal"], rate * per_vest, (tw - wd) * per_vest, tw * per_vest])
        start = [acc[-1]["next_vesting_withdrawal"], acc[-1]["name"]]
        # «нет вывода» = time_point_sec::maximum(), печатается как 1969-12-31T23:59:59 и стоит в конце порядка
        if len(acc) < 1000 or acc[-1]["next_vesting_withdrawal"][:4] in ("1969", "2106"):
            break
        time.sleep(0.3)
    json.dump({"per_vest": per_vest, "rows": rows}, open(f"{OUT}/{net}_powerdown.json", "w"))
    c = Circ(net.upper()).at(time.time() - 86400)
    week = sum(r[2] for r in rows)
    print(f"{net}: аккаунтов с power down {len(rows)}, выплата недели {week:,.0f} ({100 * week / c:.3f}% обращения), "
          f"осталось всего {sum(r[3] for r in rows):,.0f} ({100 * sum(r[3] for r in rows) / c:.2f}%)")
    for thr in (0.0005, 0.001, 0.005):
        n_w = sum(1 for r in rows if r[2] >= thr * c)
        n_t = sum(1 for r in rows if r[4] >= thr * c)
        print(f"  ≥ {100 * thr:.2f}%: недельная часть — {n_w} аккаунтов; весь объявленный вывод — {n_t}")
    top = sorted(rows, key=lambda r: -r[4])[:5]
    print("  крупнейшие:", "; ".join(f"{r[0]} {100 * r[4] / c:.2f}% (неделя {100 * r[2] / c:.3f}%, след. {r[1][:10]})" for r in top))


if __name__ == "__main__":
    for n in NODES:
        snap(n)
