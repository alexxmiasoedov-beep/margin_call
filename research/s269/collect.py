"""s269 — сбор переводов токенов на адреса Binance в новых сетях (запись — ВЫВОДЫ.md) с докачкой с места остановки.

Сети и источники (клиенты из s267/study):
  ton   — жетоны NOT, DOGS, CATI, HMSTR через toncenter v3 (окна по 30 сут, листание по времени);
  sui   — CETUS, HAEDAL, WAL, MMT через Sui GraphQL (транзакции адресов Binance из PoR по месяцам, изменения баланса);
  rpc <сеть> <узел> <шаг> — логи ERC-20 через публичный узел сети (куски по шаг блоков);
  sqd <набор> <сеть> [native] — логи ERC-20 (и транзакции родной монеты) через SQD Portal.
Строки (перевод ≥ 0,02% нынешнего обращения CMC) — /home/user/mc_data/s269/raw_<сеть>.jsonl, сделанные куски —
prog_<сеть>.json. Период — 25.09.2024 (запас для правила 48 ч и «нового вкладчика») … 20.10.2026.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s269/collect.py <режим> …"""
import calendar
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s267", "study"))
import evm_probe as EP  # noqa: E402  (evm_sets, rpc_decimals)
import sqdx  # noqa: E402
import sui_gql as G  # noqa: E402
import ton_probe as TP  # noqa: E402  (raw, get, EXTRA)

OUT = "/home/user/mc_data/s269"
T0 = calendar.timegm(time.strptime("2024-09-25", "%Y-%m-%d"))
T1 = calendar.timegm(time.strptime("2026-10-20", "%Y-%m-%d"))
KEEP = 0.0002
NETS = json.load(open("/dev/shm/s267/nets.json"))


class Store:
    """Строки и сделанные куски одной сети; запись после каждого куска."""

    def __init__(self, net):
        os.makedirs(OUT, exist_ok=True)
        self.raw = f"{OUT}/raw_{net}.jsonl"
        self.pf = f"{OUT}/prog_{net}.json"
        self.done = set(json.load(open(self.pf))) if os.path.exists(self.pf) else set()

    def put(self, key, rows):
        with open(self.raw, "a") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        self.done.add(key)
        tmp = self.pf + ".tmp"
        json.dump(sorted(self.done), open(tmp, "w"))
        os.replace(tmp, self.pf)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def ton():
    st = Store("TON")
    por = [r["address"] for r in json.load(open("s250/por.json"))["data"] if r["network"] in ("TON", "TONMEMO")]
    binance = sorted({TP.raw(a) for a in por} | set(TP.EXTRA))
    for p in ("NOT", "DOGS", "CATI", "HMSTR"):
        r = NETS[p]; master = r["nets"]["TON"]["contract"]; circ = r["circ"]
        w0 = T0
        while w0 < T1:
            w1 = min(T1, w0 + 30 * 86400)
            key = f"{p}:{w0}"
            if key not in st.done:
                rows, cur, seen = [], w0, set()
                while cur < w1:
                    d = TP.get({"owner_address": binance, "direction": "in", "jetton_master": master, "start_utime": cur,
                                "end_utime": w1, "limit": 1000, "offset": 0, "sort": "asc"})
                    tr = d.get("jetton_transfers") or []
                    new = 0
                    for x in tr:
                        k = (x.get("transaction_hash"), x.get("source"), x.get("amount"))
                        if k in seen:
                            continue
                        seen.add(k); new += 1
                        if x.get("transaction_aborted"):
                            continue
                        amt = int(x["amount"]) / 1e9
                        if amt / circ >= KEEP:
                            rows.append({"net": "TON", "perp": p, "t": int(x["transaction_now"]), "from": TP.raw(x["source"]),
                                         "to": TP.raw(x["destination"]), "amt": amt, "tx": x.get("transaction_hash")})
                    if len(tr) < 1000 or not new:
                        cur = w1
                    else:
                        cur = max(int(x["transaction_now"]) for x in tr)
                st.put(key, rows)
                log("TON", p, time.strftime("%Y-%m-%d", time.gmtime(w0)), "строк", len(rows))
            w0 = w1
    json.dump({"binance": binance}, open(f"{OUT}/binance_TON.json", "w"))
    log("TON готово")


def month_starts():
    out, y, m = [], 2024, 9
    while True:
        t = calendar.timegm((y, m, 1, 0, 0, 0))
        out.append(max(t, T0))
        if t >= T1:
            break
        m += 1
        if m > 12:
            y, m = y + 1, 1
    out[-1] = T1
    return out


def sui():
    st = Store("SUI")
    por = sorted({r["address"] for r in json.load(open("s250/por.json"))["data"] if r["network"] == "SUI"})
    coins = {}
    for p in ("CETUS", "HAEDAL", "WAL", "MMT"):
        coins[NETS[p]["nets"]["SUI"]["contract"]] = {"perp": p, "circ": NETS[p]["circ"]}
    cpf = f"{OUT}/sui_cp.json"
    cps = json.load(open(cpf)) if os.path.exists(cpf) else {}
    for t in month_starts():
        if str(t) not in cps:
            cps[str(t)] = G.checkpoint_at(t)
            json.dump(cps, open(cpf, "w"))
    bounds = [(int(t), cps[str(t)]) for t in month_starts()]
    log("Sui: месяцев", len(bounds) - 1, "адресов", len(por))
    for a in por:
        for (ta, ca), (tb, cb) in zip(bounds[:-1], bounds[1:]):
            key = f"{a}:{ta}"
            if key in st.done:
                continue
            rows, n = [], 0
            for x in G.txs(a, ca - 1, cb + 1):
                n += 1
                eff = x["effects"]
                bcs = eff["balanceChanges"]["nodes"]
                for bc in bcs:
                    own = (bc.get("owner") or {}).get("address")
                    ct = bc["coinType"]["repr"]
                    if own not in por or ct not in coins or int(bc["amount"]) <= 0:
                        continue
                    c = coins[ct]; amt = int(bc["amount"]) / 1e9
                    if amt / c["circ"] < KEEP:
                        continue
                    src = [(bb.get("owner") or {}).get("address") for bb in bcs
                           if bb["coinType"]["repr"] == ct and int(bb["amount"]) < 0]
                    ts = calendar.timegm(time.strptime(eff["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))
                    rows.append({"net": "SUI", "perp": c["perp"], "t": ts, "to": own, "from": src[0] if src else None,
                                 "internal": not src or all(s in por for s in src), "amt": amt, "tx": x["digest"]})
            st.put(key, rows)
            log("Sui", a[:10], time.strftime("%Y-%m", time.gmtime(ta)), "транзакций", n, "строк", len(rows),
                "запросов", G.STAT["req"])
    log("Sui готово")


def evm_tokens(net, rpc=None):
    toks = {}
    for b, r in NETS.items():
        v = r["nets"].get(net)
        if not v or r["skip"] or not r.get("circ"):
            continue
        c = str(v["contract"] or "").lower()
        if c.startswith("0x") and len(c) == 42 and int(c, 16) > 0x10000:
            toks[c] = {"perp": b, "circ": r["circ"]}
    for c, x in toks.items():
        x["dec"] = EP.rpc_decimals(rpc, c) if rpc else None
    return toks


def rpc_mode(net, rpc, step):
    import rpc_probe as RP  # noqa: E402  (call, block_at)
    st = Store(net)
    binance, cex = EP.evm_sets()
    toks = evm_tokens(net, rpc)
    for c, x in toks.items():
        if x["dec"] is None:
            x["dec"] = 18
    meta = f"{OUT}/meta_{net}.json"
    if os.path.exists(meta):
        m = json.load(open(meta)); b0, b1 = m["b0"], m["b1"]
    else:
        h = int(RP.call(rpc, "eth_blockNumber", []), 16)
        b0, b1 = RP.block_at(rpc, T0, 0, h), RP.block_at(rpc, T1, 0, h)
        json.dump({"b0": b0, "b1": b1, "tokens": toks}, open(meta, "w"))
    padded = [sqdx.pad(a) for a in sorted(binance)]
    log(net, "блоки", b0, b1, "токены", sorted(x["perp"] for x in toks.values()))
    bts = {}

    def logs(fr, to):
        try:
            return RP.call(rpc, "eth_getLogs", [{"fromBlock": hex(fr), "toBlock": hex(to), "address": sorted(toks),
                                                 "topics": [sqdx.TRANSFER, None, padded]}], tries=4)
        except RuntimeError:
            if to - fr < 50:
                raise
            mid = (fr + to) // 2
            return logs(fr, mid) + logs(mid + 1, to)

    chunk = step * 20
    for c0 in range(b0, b1 + 1, chunk):
        key = str(c0)
        if key in st.done:
            continue
        rows = []
        for fr in range(c0, min(b1, c0 + chunk - 1) + 1, step):
            to = min(b1, fr + step - 1, c0 + chunk - 1)
            for lg in logs(fr, to):
                tk = toks.get(lg["address"].lower())
                if not tk or len(lg["topics"]) < 3 or "0x" + lg["topics"][2][-40:].lower() not in binance:
                    continue
                if not lg.get("data") or lg["data"] == "0x":
                    continue
                amt = int(lg["data"][:66], 16) / 10 ** tk["dec"]
                if amt / tk["circ"] < KEEP:
                    continue
                bn = int(lg["blockNumber"], 16)
                ts = int(lg.get("blockTimestamp") or "0x0", 16)
                if not ts:
                    if bn not in bts:
                        bts[bn] = sqdx.rpc_block_ts(rpc, bn)
                    ts = bts[bn]
                rows.append({"net": net, "perp": tk["perp"], "t": ts, "blk": bn, "from": "0x" + lg["topics"][1][-40:],
                             "to": "0x" + lg["topics"][2][-40:], "amt": amt, "tx": lg.get("transactionHash")})
        st.put(key, rows)
        log(net, f"{100 * (c0 - b0) / max(1, b1 - b0):.0f}%", "строк", len(rows))
    log(net, "готово")


def sqd_mode(ds, net, native=False, rpc=None):
    st = Store(net)
    binance, cex = EP.evm_sets()
    toks = evm_tokens(net, rpc)
    meta = f"{OUT}/meta_{net}.json"
    if os.path.exists(meta):
        m = json.load(open(meta)); b0, b1 = m["b0"], m["b1"]
    else:
        h = sqdx.head(ds)                       # время блоков — по самому SQD: публичный узел Avalanche старых заголовков
        b0 = sqdx.block_at(ds, T0, hi=h)        # не отдаёт (ответ без времени сдвигал поиск); узел — только для decimals()
        b1 = sqdx.block_at(ds, T1, lo=b0, hi=h)
        json.dump({"b0": b0, "b1": b1, "tokens": toks}, open(meta, "w"))
    for c, x in toks.items():
        if x["dec"] is None:
            x["dec"] = 18
    nat = None
    if native:
        nat = next(({"perp": b, "circ": r["circ"]} for b, r in NETS.items() if b == native), None)
    log(ds, net, "блоки", b0, b1, "токены", sorted(x["perp"] for x in toks.values()), "родная", nat and nat["perp"])
    padded = [sqdx.pad(a) for a in sorted(binance)]
    parts = 60
    step = (b1 - b0) // parts + 1
    for k in range(parts):
        a, b = b0 + k * step, min(b1, b0 + (k + 1) * step - 1)
        if a > b:
            break
        key = str(a)
        if key in st.done:
            continue
        rows = []
        if toks:
            q = {"fields": {"block": {"number": True, "timestamp": True},
                            "log": {"address": True, "topics": True, "data": True, "transactionHash": True}},
                 "logs": [{"address": sorted(toks), "topic0": [sqdx.TRANSFER], "topic2": padded}]}
            for blk in sqdx.stream_all(ds, a, b, q):
                ts = blk["header"]["timestamp"]
                for lg in blk.get("logs") or []:
                    tk = toks.get(lg["address"].lower())
                    if not tk or len(lg["topics"]) < 3 or not lg.get("data") or lg["data"] == "0x":
                        continue
                    amt = int(lg["data"][:66], 16) / 10 ** tk["dec"]
                    if amt / tk["circ"] >= KEEP:
                        rows.append({"net": net, "perp": tk["perp"], "t": int(ts), "blk": blk["header"]["number"],
                                     "from": "0x" + lg["topics"][1][-40:], "to": "0x" + lg["topics"][2][-40:], "amt": amt,
                                     "tx": lg.get("transactionHash")})
        if nat:
            q = {"fields": {"block": {"number": True, "timestamp": True},
                            "transaction": {"from": True, "to": True, "value": True, "hash": True}},
                 "transactions": [{"to": sorted(binance)}]}
            for blk in sqdx.stream_all(ds, a, b, q):
                ts = blk["header"]["timestamp"]
                for tx in blk.get("transactions") or []:
                    v = int(tx.get("value") or "0x0", 16) / 1e18
                    if v > 0 and v / nat["circ"] >= KEEP:
                        rows.append({"net": net, "perp": nat["perp"], "t": int(ts), "blk": blk["header"]["number"],
                                     "from": str(tx.get("from")).lower(), "to": str(tx.get("to")).lower(), "amt": v,
                                     "tx": tx.get("hash")})
        st.put(key, rows)
        log(ds, f"кусок {k + 1}/{parts}", "строк", len(rows), "запросов", sqdx.STAT["req"], "занято", sqdx.STAT["busy"])
    log(ds, "готово")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "ton":
        ton()
    elif mode == "sui":
        sui()
    elif mode == "rpc":
        rpc_mode(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif mode == "sqd":
        sqd_mode(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else False,
                 sys.argv[5] if len(sys.argv) > 5 else None)
