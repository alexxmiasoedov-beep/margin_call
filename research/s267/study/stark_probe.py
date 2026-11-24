"""s267 — проба частоты крупных заводов STRK на Binance в Starknet через публичный узел (starknet_getEvents, без ключа).

В 2026 г. у события Transfer токена STRK отправитель и получатель — в ключах (keys [Transfer, from, to], data [low, high]),
поэтому узел сам отбирает переводы на адреса Binance (фильтр keys по третьей позиции). В старом формате (2023 г.)
получатель был в данных — для ранней истории пришлось бы выгружать все переводы STRK (~90 тыс. в сутки). Адреса Binance — список
STARKNET из proof-of-reserves (`s250/por.json`). Событие — перевод на адрес Binance от адреса не из списка, ≥ 0,5%
обращения (CMC сейчас), первое за 48 ч; для картины — 0,25% и 0,1%. Доходы не считаются.

Запуск из /home/user/mc_data: python3 -I <repo>/research/s267/study/stark_probe.py <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец>"""
import calendar
import json
import sys
import time
import urllib.request

RPCS = ["https://starknet-rpc.publicnode.com", "https://api.zan.top/public/starknet-mainnet"]
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
STRK = "0x04718f5a0fc34cc1af16a1cdee98ffb20c31f5cd61d6ab07201858f4287c938d"
TRANSFER = "0x99cd8bde557814842a3121e8ddfd433a539b8c9f14bf31ebf108d12e6196e9"
GAP = 48 * 3600


def call(method, params, tries=10):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for k in range(tries):
        rpc = RPCS[k % len(RPCS)]
        try:
            time.sleep(0.2)
            r = json.loads(urllib.request.urlopen(urllib.request.Request(rpc, data=body, headers=UA), timeout=90).read())
            if "error" in r:
                raise RuntimeError(str(r["error"])[:200])
            return r["result"]
        except Exception:  # noqa: BLE001
            time.sleep(2 + 3 * k)
    raise RuntimeError(f"Starknet: нет ответа на {method}")


def block_ts(n):
    return call("starknet_getBlockWithTxHashes", [{"block_number": n}])["timestamp"]


def block_at(ts):
    lo, hi = 0, call("starknet_blockNumber", [])
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if block_ts(mid) >= ts:
            hi = mid
        else:
            lo = mid
    return hi


def main():
    d0, d1 = sys.argv[1:3]
    t0, t1 = (calendar.timegm(time.strptime(x, "%Y-%m-%d")) for x in (d0, d1))
    circ = json.load(open("/dev/shm/s267/nets.json"))["STRK"]["circ"]
    por = {int(r["address"], 16) for r in json.load(open("s250/por.json"))["data"] if r["network"] == "STARKNET"}
    b0, b1 = block_at(t0), block_at(t1)
    print(f"STRK: блоки {b0}–{b1}; адресов Binance {len(por)}", flush=True)
    rows, n, total, tok, tt = [], 0, 0, None, time.time()
    while True:
        flt = {"from_block": {"block_number": b0}, "to_block": {"block_number": b1}, "address": STRK,
               "keys": [[TRANSFER], [], [hex(a) for a in sorted(por)]], "chunk_size": 1000}
        if tok:
            flt["continuation_token"] = tok
        r = call("starknet_getEvents", {"filter": flt})
        n += 1
        for e in r["events"]:
            d, ks = e["data"], e["keys"]
            if len(ks) >= 3:          # формат Cairo 1 (с 2024 г.): from, to — в ключах, сумма — в данных
                frm, to, lo, hi = int(ks[1], 16), int(ks[2], 16), int(d[0], 16), int(d[1], 16) if len(d) > 1 else 0
            elif len(d) >= 3:         # старый формат: всё в данных
                frm, to, lo, hi = int(d[0], 16), int(d[1], 16), int(d[2], 16), int(d[3], 16) if len(d) > 3 else 0
            else:
                continue
            total += 1
            if to not in por:
                continue
            amt = (lo + (hi << 128)) / 1e18
            rows.append({"t": e["block_number"], "from": hex(frm), "to": hex(to), "amt": amt, "share": amt / circ,
                         "internal": frm in por, "tx": e.get("transaction_hash")})
        tok = r.get("continuation_token")
        if n % 200 == 0:
            print(f"  … запросов {n}, переводов STRK {total}, на Binance {len(rows)}, {time.time() - tt:.0f} с", flush=True)
        if not tok:
            break
    # время событий: блок → время (по одному запросу на крупный перевод)
    for r in rows:
        if r["share"] >= 0.001:
            r["ts"] = block_ts(r["t"])
    days = (t1 - t0) / 86400
    summ = {}
    for thr in (0.005, 0.0025, 0.001):
        ev, last = [], -10 ** 12
        for r in sorted([x for x in rows if "ts" in x], key=lambda z: z["ts"]):
            if r["share"] < thr or r["internal"]:
                continue
            if r["ts"] - last >= GAP:
                ev.append(r)
            last = r["ts"]
        summ[str(thr)] = {"events": len(ev), "per_month": round(len(ev) / days * 30.4, 1)}
    out = {"d0": d0, "d1": d1, "days": days, "blocks": [b0, b1], "requests": n, "strk_transfers": total,
           "to_binance": len(rows), "summary": summ, "top": sorted(rows, key=lambda z: -z["share"])[:25]}
    json.dump(out, open(f"s267/probe_STARKNET_{d0}.json", "w"), indent=0)
    print(f"STARKNET {d0}…{d1} ({days:.0f} сут): переводов STRK {total}, на Binance {len(rows)} "
          f"(внутренних {sum(r['internal'] for r in rows)}); ≥0,5% — {summ['0.005']['events']} ({summ['0.005']['per_month']} в мес.); "
          f"≥0,25% — {summ['0.0025']['per_month']}; ≥0,1% — {summ['0.001']['per_month']} в мес.; запросов {n}, "
          f"{time.time() - tt:.0f} с", flush=True)


if __name__ == "__main__":
    main()
