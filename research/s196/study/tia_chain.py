"""s196 — цепочка ключей на Celestia (без цен): крупный анбондинг (делегатор ≥ 0,1% обращения за сутки завершения, снимки
архива) → что делает держатель с монетами в 30 сут после завершения: отправка с мемо (депозит на биржу: у бирж Cosmos один
адрес + мемо-тег), IBC-перевод, повторный стейкинг, перевод без мемо. Архивный LCD Numia (без ключа),
cosmos/tx/v1beta1/txs?query=transfer.sender='…' (и message.sender для MsgDelegate). Итог — лог и tia_chain.json."""
import calendar
import collections
import json
import re
import time
import urllib.parse
from common196 import http, OUT, DAY

LCD = "https://public-celestia-lcd.numia.xyz"


def tparse(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def txs(q):
    out, page = [], 1
    while page <= 5:
        d = http(f"{LCD}/cosmos/tx/v1beta1/txs?query={urllib.parse.quote(q)}&pagination.limit=100&page={page}"
                 f"&order_by=ORDER_BY_ASC", timeout=60, tries=2)
        if not d:
            break
        tr = d.get("tx_responses") or []
        out += list(zip(d.get("txs") or [], tr))
        if len(tr) < 100:
            break
        page += 1
    return out


def classify(addr, t0, t1):
    res = collections.Counter()
    seen = set()
    for q in (f"transfer.sender='{addr}'", f"message.sender='{addr}'"):
        for tx, r in txs(q):
            h = r["txhash"]
            if h in seen:
                continue
            seen.add(h)
            t = tparse(r["timestamp"])
            if not (t0 <= t <= t1) or r.get("code"):
                continue
            res["_first"] = min(res.get("_first", 1e12), (t - t0) / DAY)
            memo = (tx["body"].get("memo") or "").strip()
            for m in tx["body"]["messages"]:
                ty = m["@type"]
                if ty.endswith("MsgSend") and m.get("from_address") == addr:
                    amt = sum(int(a["amount"]) for a in m["amount"] if a["denom"] == "utia") / 1e6
                    key = "мемо (биржа)" if re.fullmatch(r"[0-9A-Za-z]{4,20}", memo or "") else "перевод без мемо"
                    res[key] += amt
                elif ty.endswith("MsgTransfer") and m.get("sender") == addr:
                    tok = m.get("token") or {}
                    if tok.get("denom") == "utia":
                        res["IBC"] += int(tok["amount"]) / 1e6
                elif ty.endswith("MsgDelegate") and m.get("delegator_address") == addr:
                    res["снова в стейк"] += int(m["amount"]["amount"]) / 1e6
                elif ty.endswith("MsgMultiSend"):
                    for i in m.get("inputs") or []:
                        if i["address"] == addr:
                            res["multisend"] += sum(int(a["amount"]) for a in i["coins"] if a["denom"] == "utia") / 1e6
    return res


def main():
    big = json.load(open(f"{OUT}/tia_big_unbond.json"))
    import os
    p = f"{OUT}/tia_chain.json"
    done = json.load(open(p)) if os.path.exists(p) else {}
    tot = collections.Counter()
    unb_tot = 0.0
    part1 = {}
    if os.path.exists(f"{OUT}/tia_chain_part1.json"):
        part1 = json.load(open(f"{OUT}/tia_chain_part1.json"))     # первая часть прогона (адрес — 16 знаков)
    for frac, addr, day, snap in big:
        if f"{addr[:16]}:{day}" in part1:
            continue
        t0 = calendar.timegm(time.strptime(day, "%Y-%m-%d"))
        if t0 + 30 * DAY > time.time():
            continue
        key = f"{addr}:{day}"
        if key in done:
            continue
        r = classify(addr, t0, t0 + 30 * DAY)
        done[key] = dict(frac=frac, day=day, out=dict(r))
        first = r.pop("_first", None)
        done[key]["first"] = first
        done[key]["out"] = dict(r)
        tot.update({k: v for k, v in r.items()})
        print(f"{day} {frac * 100:.2f}% {addr[:16]}… первая исходящая через {first if first is None else round(first, 1)} сут → "
              + ", ".join(f"{k} {v:,.0f}" for k, v in r.most_common()), flush=True)
        json.dump(done, open(p, "w"))
        time.sleep(0.2)
    json.dump(done, open(p, "w"))
    for k, v in part1.items():
        done.setdefault(k, v)
    n = len(done)
    has_memo = sum(1 for v in done.values() if v["out"].get("мемо (биржа)", 0) > 0)
    restake = sum(1 for v in done.values() if v["out"].get("снова в стейк", 0) > 0)
    fs = sorted(v["first"] for v in done.values() if v.get("first") is not None)
    if fs:
        print(f"первая исходящая после завершения: медиана {fs[len(fs) // 2]:.1f} сут, в первые 2 сут — "
              f"{sum(f <= 2 for f in fs)} из {len(done)}")
    quiet = sum(1 for v in done.values() if not v["out"])
    print(f"\nсобытий {n}: с отправкой по мемо (биржа) {has_memo}, снова в стейк {restake}, без исходящих {quiet}")
    print("сумма по видам (TIA):", ", ".join(f"{k} {v:,.0f}" for k, v in tot.most_common()))


if __name__ == "__main__":
    main()
