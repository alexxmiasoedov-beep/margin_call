"""s267 — проба частоты крупных заводов токенов TRC-20 на Binance через SQD Portal (набор tron-mainnet, без ключа).

У Binance в Tron у клиента свой адрес пополнения (`sameAddress: false`), пополнения сметаются на горячие кошельки.
Адреса Binance — список TRX из proof-of-reserves (`s250/por.json`). Токены — перпы с вводом Binance в сети TRX и адресом
контракта (SUN, JST; сам TRX — родная монета, 0,5% обращения ≈ 150 млн $, не берётся). Событие — перевод на адрес Binance
от адреса не из списка, сумма ≥ 0,5% обращения (CMC сейчас), первое у монеты за 48 ч; для картины — 0,25% и 0,1%.
Доходы не считаются.

Запуск из /home/user/mc_data: python3 -I <repo>/research/s267/study/tron_probe.py <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец>
Итог — /home/user/mc_data/s267/probe_TRX_<начало>.json и сводка на экран."""
import calendar
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sqdx  # noqa: E402

DS = "tron-mainnet"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
GAP = 48 * 3600
DEC = {"SUN": 18, "JST": 18}


def b58hex(a):
    n = 0
    for ch in a:
        n = n * 58 + B58.index(ch)
    raw = n.to_bytes(25, "big")
    assert hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4] == raw[21:], a
    return raw[1:21].hex()


def day(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%d"))


def main():
    d0, d1 = sys.argv[1:3]
    t0, t1 = day(d0), min(day(d1), int(time.time()) - 600)
    nets = json.load(open("/dev/shm/s267/nets.json"))
    por = sorted({b58hex(r["address"]) for r in json.load(open("s250/por.json"))["data"] if r["network"] == "TRX"})
    toks = {}
    for b, r in nets.items():
        v = r["nets"].get("TRX")
        if v and v["contract"] and not r["skip"] and r.get("circ"):
            toks[b58hex(v["contract"])] = {"perp": b, "circ": r["circ"]}
    h = sqdx.head(DS)
    b0 = sqdx.block_at(DS, t0, hi=h, kind="tron")
    b1 = sqdx.block_at(DS, t1, lo=b0, hi=h, kind="tron")
    print(f"Tron {d0}…{d1}: блоки {b0}–{b1}; токены {[t['perp'] for t in toks.values()]}; адресов Binance {len(por)}", flush=True)
    q = {"fields": {"block": {"number": True, "timestamp": True},
                    "log": {"address": True, "topics": True, "data": True, "transactionIndex": True}},
         "logs": [{"address": sorted(toks), "topic0": [sqdx.TRANSFER[2:]], "topic2": ["0" * 24 + a for a in por]}]}
    t = time.time()
    rows = []
    for blk in sqdx.stream_all(DS, b0, b1, q, deadline=time.time() + 3 * 3600, kind="tron"):
        ts = blk["header"]["timestamp"] / 1000
        for lg in blk.get("logs") or []:
            tk = toks.get(lg["address"])
            if not tk or len(lg["topics"]) < 3 or not lg.get("data"):
                continue
            amt = int(lg["data"][:64], 16) / 10 ** DEC.get(tk["perp"], 18)
            rows.append({"perp": tk["perp"], "t": ts, "from": lg["topics"][1][-40:], "to": lg["topics"][2][-40:],
                         "amt": amt, "share": amt / tk["circ"]})
    days = (t1 - t0) / 86400
    pset = set(por)
    out = {"d0": d0, "d1": d1, "days": days, "blocks": [b0, b1], "n_rows": len(rows), "sec": round(time.time() - t)}
    summ = {}
    for thr in (0.005, 0.0025, 0.001):
        ev, last = [], {}
        for r in sorted(rows, key=lambda z: z["t"]):
            if r["share"] < thr or r["from"] in pset:
                continue
            if r["t"] - last.get(r["perp"], -10 ** 12) >= GAP:
                ev.append(r)
            last[r["perp"]] = r["t"]
        summ[str(thr)] = {"events": len(ev), "per_month": round(len(ev) / days * 30.4, 1),
                          "by_perp": {p: sum(1 for e in ev if e["perp"] == p) for p in sorted({e["perp"] for e in ev})}}
    out["summary"] = summ
    out["internal_big"] = sum(1 for r in rows if r["share"] >= 0.005 and r["from"] in pset)
    out["top"] = sorted([r for r in rows if r["from"] not in pset], key=lambda z: -z["share"])[:25]
    out["recv"] = {}
    for r in rows:
        out["recv"][r["to"]] = out["recv"].get(r["to"], 0) + 1
    json.dump(out, open(f"s267/probe_TRX_{d0}.json", "w"), indent=0)
    print(f"TRX {d0}…{d1} ({days:.0f} сут): переводов {len(rows)}; ≥0,5% — {summ['0.005']['events']} "
          f"({summ['0.005']['per_month']} в мес., {summ['0.005']['by_perp']}); ≥0,25% — {summ['0.0025']['per_month']}; "
          f"≥0,1% — {summ['0.001']['per_month']} в мес.; внутренних ≥0,5% {out['internal_big']}; {out['sec']} с; "
          f"запросов {sqdx.STAT['req']}", flush=True)


if __name__ == "__main__":
    main()
