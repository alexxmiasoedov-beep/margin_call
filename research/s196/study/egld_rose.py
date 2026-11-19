"""s196 — анбондинг MultiversX (EGLD, 10 эпох ≈ 10 сут) и Oasis (ROSE, 336 эпох ≈ 14 сут) по открытым API без ключа.
Выборка: первые 7 суток каждого месяца (частоты масштабируются ×30,4/7).
- EGLD: api.multiversx.com/transactions?function=unDelegate (сумма — в data «unDelegate@<hex>», 1e18), с 2021 г.
- ROSE: nexus.oasis.io/v1/consensus/transactions?method=staking.ReclaimEscrow (доли; сумма = доли × курс доли ≥ 1),
  для крупных — точная сумма и эпоха конца из события staking.escrow.debonding_start (по tx_hash); с 04.2022 (Damask).
Итог — /home/user/mc_data/s196/egld_undelegate.json, rose_reclaim.json."""
import base64
import calendar
import json
import os
import sys
import time
from common196 import http, OUT


def month_starts(y0=2020, m0=10, y1=2026, m1=11):
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        yield calendar.timegm((y, m, 1, 0, 0, 0))
        m += 1
        if m > 12:
            y, m = y + 1, 1


def egld():
    p = f"{OUT}/egld_undelegate.json"
    out = json.load(open(p)) if os.path.exists(p) else {}
    for t0 in month_starts(2021, 1):
        for k in range(7):
            a = t0 + k * 86400
            key = str(a)
            if key in out or a > time.time() - 86400:
                continue
            rows, frm = [], 0
            while True:
                d = http(f"https://api.multiversx.com/transactions?function=unDelegate&status=success&after={a}&before={a + 86400}"
                         f"&from={frm}&size=1000&fields=txHash,timestamp,sender,receiver,data")
                if d is None:
                    break
                for x in d:
                    try:
                        s = base64.b64decode(x.get("data") or "").decode()
                        amt = int(s.split("@")[1], 16) / 1e18 if "@" in s and s.split("@")[1] else None
                    except Exception:
                        amt = None
                    rows.append([x["timestamp"], x["sender"], x["receiver"], amt])
                if len(d) < 1000 or frm + 1000 >= 10000:
                    break
                frm += 1000
            out[key] = rows
            time.sleep(0.2)
        json.dump(out, open(p, "w"))
        print("EGLD", time.strftime("%Y-%m", time.gmtime(t0)), "транзакций за 7 сут", sum(len(out.get(str(t0 + k * 86400), [])) for k in range(7)), flush=True)
    return out


def rose():
    p = f"{OUT}/rose_reclaim.json"
    out = json.load(open(p)) if os.path.exists(p) else {}
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
    for t0 in month_starts(2022, 5):
        for k in range(7):
            a = t0 + k * 86400
            key = str(a)
            if key in out or a > time.time() - 86400:
                continue
            rows, off = [], 0
            while True:
                d = http(f"https://nexus.oasis.io/v1/consensus/transactions?method=staking.ReclaimEscrow&after={iso(a)}"
                         f"&before={iso(a + 86400)}&limit=200&offset={off}", timeout=90)
                if not d:
                    break
                tx = d.get("transactions") or []
                for x in tx:
                    if not x.get("success", True):
                        continue
                    rows.append([x["timestamp"], x["sender"], (x.get("body") or {}).get("account"),
                                 int((x.get("body") or {}).get("shares") or 0) / 1e9, x["hash"]])
                if len(tx) < 200:
                    break
                off += 200
            out[key] = rows
            time.sleep(0.2)
        json.dump(out, open(p, "w"))
        print("ROSE", time.strftime("%Y-%m", time.gmtime(t0)), "транзакций за 7 сут", sum(len(out.get(str(t0 + k * 86400), [])) for k in range(7)), flush=True)
    return out


def rose_exact(min_shares):
    """точная сумма и эпоха конца для крупных: событие staking.escrow.debonding_start по tx_hash."""
    p = f"{OUT}/rose_reclaim.json"
    out = json.load(open(p))
    q = f"{OUT}/rose_exact.json"
    ex = json.load(open(q)) if os.path.exists(q) else {}
    for rows in out.values():
        for r in rows:
            if r[3] >= min_shares and r[4] not in ex:
                d = http(f"https://nexus.oasis.io/v1/consensus/events?tx_hash={r[4]}&type=staking.escrow.debonding_start")
                ev = ((d or {}).get("events") or [{}])[0].get("body") or {}
                ex[r[4]] = [int(ev.get("amount") or 0) / 1e9, ev.get("debond_end_time")]
                time.sleep(0.1)
    json.dump(ex, open(q, "w"))
    return ex


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    if what in ("egld", "both"):
        egld()
    if what in ("rose", "both"):
        rose()
    if what == "rose_exact":
        rose_exact(float(sys.argv[2]))
