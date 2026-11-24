"""s267 — проба частоты крупных заводов на Binance в сетях EVM через SQD Portal (без ключа).

Для сети и окна [T0, T1]:
- адреса Binance — объединение всех адресов EVM из proof-of-reserves Binance (`s250/por.json`, все сети EVM: у Binance
  один ключ на все сети EVM, поэтому адрес Binance в одной сети — адрес Binance и в другой) и меток Binance
  `bot/cex_labels.tsv`;
- токены — перпы, у которых Binance принимает ввод в этой сети (`/dev/shm/s267/nets.json`), адрес контракта — из сетей
  ввода Binance; родная монета сети (контракта нет) — по транзакциям с value;
- событие — перевод на адрес Binance от адреса, который не биржа (метки `bot/cex_labels.tsv` и адреса Binance), сумма
  ≥ 0,5% монет в обращении (CMC сейчас — грубо для пробы), первое у монеты за 48 ч. Для картины считаются и пороги 0,25%
  и 0,1%.
Доходы не считаются.

Запуск из /home/user/mc_data:
  python3 -I <repo>/research/s267/study/evm_probe.py <набор SQD> <сеть Binance> <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец> [rpc]
Итог — /home/user/mc_data/s267/probe_<сеть>_<начало>.json и строка сводки на экран."""
import calendar
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sqdx  # noqa: E402

LAB = os.path.join(HERE, "..", "..", "..", "bot", "cex_labels.tsv")
GAP = 48 * 3600
# Родная монета сети с адресом-«обёрткой» в getNetworkCoinAll: перевод CELO в сети Celo — это value транзакции, а логи
# Transfer контракта 0x471e… появляются только при вызове контракта (в пробе по логам — 3 перевода на Binance за 61 сут).
FORCE_NATIVE = {("CELO", "CELO")}


def evm_sets():
    por = json.load(open("s250/por.json"))["data"]
    binance = {r["address"].lower() for r in por if str(r["address"]).lower().startswith("0x") and len(r["address"]) == 42}
    cex = set()
    for line in open(LAB):
        if line.strip() and not line.startswith("#"):
            a, ex = line.split("\t")[:2]
            cex.add(a.lower())
            if ex.lower() == "binance":
                binance.add(a.lower())
    return binance, cex | binance


def rpc_decimals(rpc, token):
    if not rpc:
        return None
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": token, "data": "0x313ce567"}, "latest"]}).encode()
    for _ in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(rpc, data=body, headers=sqdx.UA), timeout=30)
            res = json.loads(r.read()).get("result")
            return int(res, 16) if res and res != "0x" else None
        except Exception:  # noqa: BLE001
            time.sleep(3)
    return None


def progress_printer(b0, b1):
    st = {"t": time.time(), "n": 0}

    def f(cur):
        st["n"] += 1
        if time.time() - st["t"] > 60:
            st["t"] = time.time()
            print(f"  … блок {cur} ({100 * (cur - b0) / max(1, b1 - b0):.0f}%), запросов {sqdx.STAT['req']}, "
                  f"занято {sqdx.STAT['busy']}", flush=True)
    return f


def day(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%d"))


def main():
    ds, net, d0, d1 = sys.argv[1:5]
    rpc = sys.argv[5] if len(sys.argv) > 5 else None
    t0, t1 = day(d0), day(d1)
    nets = json.load(open("/dev/shm/s267/nets.json"))
    binance, cex = evm_sets()
    toks, natives = {}, []
    for b, r in nets.items():
        v = r["nets"].get(net)
        if not v or r["skip"] or not r.get("circ"):
            continue
        c = str(v["contract"] or "").lower()
        if c.startswith("0x") and len(c) == 42 and int(c, 16) > 0x10000 and (net, b) not in FORCE_NATIVE:
            toks[c] = {"perp": b, "circ": r["circ"], "price": r["price"]}
        elif r["coin"] not in ("ETH",):
            natives.append({"perp": b, "circ": r["circ"], "price": r["price"]})
    for c, x in toks.items():
        x["dec"] = rpc_decimals(rpc, c)
    h = sqdx.head(ds)
    b0 = sqdx.block_at(ds, t0, hi=h, rpc=rpc)
    b1 = sqdx.block_at(ds, t1, lo=b0, hi=h, rpc=rpc) if t1 < time.time() - 600 else h
    print(f"{ds} {net}: блоки {b0}–{b1}; токенов {len(toks)}, родных {len(natives)}; адресов Binance {len(binance)}",
          flush=True)
    t = time.time()
    rows = []
    padded = [sqdx.pad(a) for a in sorted(binance)]
    if toks:
        q = {"fields": {"block": {"number": True, "timestamp": True},
                        "log": {"address": True, "topics": True, "data": True, "transactionHash": True}},
             "logs": [{"address": sorted(toks), "topic0": [sqdx.TRANSFER], "topic2": padded}]}
        prog = progress_printer(b0, b1)
        for blk in sqdx.stream_all(ds, b0, b1, q, deadline=time.time() + 3 * 3600, progress=prog):
            ts = blk["header"]["timestamp"]
            for lg in blk.get("logs") or []:
                tk = toks.get(lg["address"].lower())
                if not tk or len(lg["topics"]) < 3 or not lg.get("data") or lg["data"] == "0x":
                    continue
                amt = int(lg["data"][:66], 16) / 10 ** (tk.get("dec") or 18)
                rows.append({"perp": tk["perp"], "t": ts, "from": "0x" + lg["topics"][1][-40:], "to": "0x" + lg["topics"][2][-40:],
                             "amt": amt, "share": amt / tk["circ"], "tx": lg.get("transactionHash")})
    if natives:
        q = {"fields": {"block": {"number": True, "timestamp": True},
                        "transaction": {"from": True, "to": True, "value": True, "hash": True}},
             "transactions": [{"to": sorted(binance)}]}
        nat = natives[0]
        prog = progress_printer(b0, b1)
        for blk in sqdx.stream_all(ds, b0, b1, q, deadline=time.time() + 3 * 3600, progress=prog):
            ts = blk["header"]["timestamp"]
            for tx in blk.get("transactions") or []:
                v = int(tx.get("value") or "0x0", 16) / 1e18
                if v <= 0:
                    continue
                rows.append({"perp": nat["perp"], "t": ts, "from": str(tx.get("from")).lower(), "to": str(tx.get("to")).lower(),
                             "amt": v, "share": v / nat["circ"], "tx": tx.get("hash")})
    days = (min(t1, time.time()) - t0) / 86400
    out = {"ds": ds, "net": net, "d0": d0, "d1": d1, "days": days, "blocks": [b0, b1], "tokens": toks, "natives": natives,
           "n_rows": len(rows), "sec": round(time.time() - t), "req": dict(sqdx.STAT)}
    summ = {}
    for thr in (0.005, 0.0025, 0.001):
        ev, last = [], {}
        for r in sorted(rows, key=lambda z: z["t"]):
            if r["share"] < thr or r["from"] in cex:
                continue
            if r["t"] - last.get(r["perp"], -10 ** 12) >= GAP:
                ev.append(r)
            last[r["perp"]] = r["t"]
        summ[str(thr)] = {"events": len(ev), "per_month": round(len(ev) / days * 30.4, 1),
                          "by_perp": {p: sum(1 for e in ev if e["perp"] == p) for p in sorted({e["perp"] for e in ev})}}
    out["summary"] = summ
    out["internal_big"] = sum(1 for r in rows if r["share"] >= 0.005 and r["from"] in cex)
    out["top"] = sorted([r for r in rows if r["from"] not in cex], key=lambda z: -z["share"])[:25]
    out["recv"] = {}
    for r in rows:
        out["recv"][r["to"]] = out["recv"].get(r["to"], 0) + 1
    os.makedirs("s267", exist_ok=True)
    json.dump(out, open(f"s267/probe_{net}_{d0}.json", "w"), indent=0)
    print(f"{net} {d0}…{d1} ({days:.0f} сут): переводов на Binance {len(rows)}; ≥0,5% — {summ['0.005']['events']} "
          f"({summ['0.005']['per_month']} в мес., {summ['0.005']['by_perp']}); ≥0,25% — {summ['0.0025']['per_month']} в мес.; "
          f"≥0,1% — {summ['0.001']['per_month']} в мес.; внутренних ≥0,5% {out['internal_big']}; {out['sec']} с, "
          f"запросов {sqdx.STAT['req']} (занято {sqdx.STAT['busy']})", flush=True)


if __name__ == "__main__":
    main()
