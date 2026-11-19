"""s196 — AVAX «сейчас»: platform.getCurrentValidators (api.avax.network/ext/bc/P, без ключа) — все текущие ставки
валидаторов и делегаторов с датой конца, записанной при создании. Календарь вперёд: концы ставок по суткам и крупные
единичные ставки (≥ порога обращения CMC), без доходов."""
import collections
import json
import time
from common196 import OUT, DAY
from freq_lib import Circ, fmt_t

d = json.load(open(f"{OUT}/avax_current.json"))["result"]["validators"]
c = Circ("AVAX").at(time.time() - DAY)
now = time.time()
rows = []
for v in d:
    amt = int(v.get("stakeAmount") or v.get("weight") or 0) / 1e9
    rows.append(("validator", v["nodeID"], amt, int(v["endTime"]), int(v["startTime"])))
    for dl in v.get("delegators") or []:
        rows.append(("delegator", (dl.get("rewardOwner") or {}).get("addresses", [""])[0], int(dl["stakeAmount"]) / 1e9,
                     int(dl["endTime"]), int(dl["startTime"])))
tot = sum(r[2] for r in rows)
print(f"AVAX: ставок {len(rows)} (валидаторов {sum(r[0] == 'validator' for r in rows)}), всего {tot:,.0f} AVAX "
      f"({100 * tot / c:.1f}% обращения {c:,.0f})")
dur = sorted((r[3] - r[4]) / DAY for r in rows)
print(f"  срок ставки: медиана {dur[len(dur) // 2]:.0f} сут, p10 {dur[len(dur) // 10]:.0f}, p90 {dur[9 * len(dur) // 10]:.0f}")
for H in (30, 90):
    sel = [r for r in rows if now < r[3] <= now + H * DAY]
    big = {th: sum(1 for r in sel if r[2] >= th * c) for th in (0.0005, 0.001, 0.005)}
    byday = collections.defaultdict(float)
    for r in sel:
        byday[int(r[3] // DAY)] += r[2]
    dbig = {th: sum(1 for v in byday.values() if v >= th * c) for th in (0.001, 0.005)}
    print(f"  концы в ближайшие {H} сут: {len(sel)} ставок, {sum(r[2] for r in sel):,.0f} AVAX; единичные ≥0,05/0,1/0,5%: "
          f"{big[0.0005]}/{big[0.001]}/{big[0.005]} ({big[0.001] / H * 30.4:.1f} в мес ≥0,1%); сутки ≥0,1/0,5%: {dbig[0.001]}/{dbig[0.005]}")
top = sorted(rows, key=lambda r: -r[2])[:6]
print("  крупнейшие ставки:", "; ".join(f"{r[0]} {100 * r[2] / c:.2f}% до {fmt_t(r[3])}" for r in top))
