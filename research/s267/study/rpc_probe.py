"""s267 — проба частоты крупных заводов на Binance в сетях EVM, которых нет в SQD Portal, через публичный узел сети
(`eth_getLogs` кусками; у Ronin предел — 200 блоков на запрос). Правило — как в evm_probe.py: перевод токена на адрес
Binance (объединение адресов EVM из proof-of-reserves и меток Binance) от адреса не из меток бирж, ≥ 0,5% обращения
(CMC сейчас), первое у монеты за 48 ч; для картины — 0,25% и 0,1%. Родные монеты сетей (без логов) не берутся.
Доходы не считаются.

Запуск из /home/user/mc_data:
  python3 -I <repo>/research/s267/study/rpc_probe.py <сеть Binance> <rpc> <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец> [кусок блоков]"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evm_probe as E  # noqa: E402
import sqdx  # noqa: E402

GAP = 48 * 3600


def call(rpc, method, params, tries=8):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for k in range(tries):
        try:
            time.sleep(0.25)
            r = json.loads(urllib.request.urlopen(urllib.request.Request(rpc, data=body, headers=sqdx.UA), timeout=60).read())
            if "error" in r:
                raise RuntimeError(str(r["error"])[:200])
            return r["result"]
        except Exception:  # noqa: BLE001
            time.sleep(2 + 3 * k)
    raise RuntimeError(f"{rpc}: нет ответа на {method}")


def block_at(rpc, ts, lo, hi):
    while hi - lo > 1:
        mid = (lo + hi) // 2
        t = sqdx.rpc_block_ts(rpc, mid)
        if t is not None and t >= ts:   # нет заголовка (узел обрезал старые блоки) — считаем, что блок старше цели
            hi = mid
        else:
            lo = mid
    return hi


def main():
    net, rpc, d0, d1 = sys.argv[1:5]
    step = int(sys.argv[5]) if len(sys.argv) > 5 else 200
    t0, t1 = E.day(d0), min(E.day(d1), int(time.time()) - 600)
    nets = json.load(open("/dev/shm/s267/nets.json"))
    binance, cex = E.evm_sets()
    toks = {}
    for b, r in nets.items():
        v = r["nets"].get(net)
        if not v or r["skip"] or not r.get("circ"):
            continue
        c = str(v["contract"] or "").lower()
        if c.startswith("0x") and len(c) == 42 and int(c, 16) > 0x10000:
            toks[c] = {"perp": b, "circ": r["circ"], "dec": E.rpc_decimals(rpc, c) or 18}
    h = int(call(rpc, "eth_blockNumber", []), 16)
    b0, b1 = block_at(rpc, t0, 0, h), block_at(rpc, t1, 0, h)
    print(f"{net}: блоки {b0}–{b1} ({b1 - b0} блоков, кусок {step}); токены {[(t['perp'], t['dec']) for t in toks.values()]}",
          flush=True)
    padded = [sqdx.pad(a) for a in sorted(binance)]
    rows, n, tt, bts = [], 0, time.time(), {}

    def logs(fr, to):
        """eth_getLogs на [fr, to]; если узел не отвечает — делим кусок пополам (до 50 блоков)."""
        nonlocal n
        try:
            n += 1
            return call(rpc, "eth_getLogs", [{"fromBlock": hex(fr), "toBlock": hex(to), "address": sorted(toks),
                                              "topics": [sqdx.TRANSFER, None, padded]}], tries=4)
        except RuntimeError:
            if to - fr < 50:
                raise
            mid = (fr + to) // 2
            return logs(fr, mid) + logs(mid + 1, to)

    for fr in range(b0, b1 + 1, step):
        to = min(b1, fr + step - 1)
        res = logs(fr, to)
        for lg in res:
            tk = toks.get(lg["address"].lower())
            if not tk or len(lg["topics"]) < 3 or "0x" + lg["topics"][2][-40:].lower() not in binance:
                continue
            amt = int(lg["data"][:66], 16) / 10 ** tk["dec"]
            ts = int(lg.get("blockTimestamp") or "0x0", 16)
            if not ts and amt / tk["circ"] >= 0.0005:   # нет blockTimestamp в логах — время блока запросом (кэш),
                # только для переводов ≥ 0,05% обращения: остальные в пороги не попадают
                bn = int(lg["blockNumber"], 16)
                if bn not in bts:
                    bts[bn] = sqdx.rpc_block_ts(rpc, bn)
                ts = bts[bn]
            rows.append({"perp": tk["perp"], "t": ts, "from": "0x" + lg["topics"][1][-40:], "to": "0x" + lg["topics"][2][-40:],
                         "amt": amt, "share": amt / tk["circ"], "tx": lg.get("transactionHash")})
        if n % 500 == 0:
            print(f"  … {100 * (to - b0) / max(1, b1 - b0):.0f}%, запросов {n}, переводов {len(rows)}, {time.time() - tt:.0f} с",
                  flush=True)
    days = (t1 - t0) / 86400
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
    out = {"net": net, "d0": d0, "d1": d1, "days": days, "blocks": [b0, b1], "tokens": toks, "n_rows": len(rows),
           "requests": n, "sec": round(time.time() - tt), "summary": summ,
           "top": sorted([r for r in rows if r["from"] not in cex], key=lambda z: -z["share"])[:25]}
    out["recv"] = {}
    for r in rows:
        out["recv"][r["to"]] = out["recv"].get(r["to"], 0) + 1
    json.dump(out, open(f"s267/probe_{net}_{d0}.json", "w"), indent=0)
    print(f"{net} {d0}…{d1} ({days:.0f} сут): переводов на Binance {len(rows)}; ≥0,5% — {summ['0.005']['events']} "
          f"({summ['0.005']['per_month']} в мес., {summ['0.005']['by_perp']}); ≥0,25% — {summ['0.0025']['per_month']}; "
          f"≥0,1% — {summ['0.001']['per_month']} в мес.; запросов {n}, {out['sec']} с", flush=True)


if __name__ == "__main__":
    main()
