"""s267 — проба крупных заводов родной монеты сети на Binance через обозреватель Blockscout (API v2, без ключа).

Для родных монет (CELO, PLUME) логов Transfer нет — смотрим входящие транзакции на адреса Binance (объединение адресов EVM
из proof-of-reserves и меток Binance; у Binance один ключ на все сети EVM): `/api/v2/addresses/<адрес>/transactions?filter=to`,
страницы по 50, от новых к старым до начала окна. Событие — value ≥ 0,5% обращения (CMC сейчас) от адреса не из меток
бирж, первое за 48 ч; для картины — 0,25% и 0,1%. Доходы не считаются.

Запуск из /home/user/mc_data: python3 -I <repo>/research/s267/study/bs_probe.py <сеть Binance> <перп> <https://обозреватель>
                                  <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец>"""
import calendar
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evm_probe as E  # noqa: E402

UA = {"User-Agent": "research-script/1.0"}
GAP = 48 * 3600


def get(url, tries=6):
    for k in range(tries):
        try:
            time.sleep(0.5)
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except Exception:  # noqa: BLE001
            time.sleep(3 + 4 * k)
    raise RuntimeError("Blockscout: нет ответа " + url[:120])


def main():
    net, perp, base, d0, d1 = sys.argv[1:6]
    t0, t1 = E.day(d0), min(E.day(d1), int(time.time()))
    r = json.load(open("/dev/shm/s267/nets.json"))[perp]
    circ = r["circ"]
    binance, cex = E.evm_sets()
    por = sorted({x["address"].lower() for x in json.load(open("s250/por.json"))["data"] if x["network"] == net})
    rows, pages, tt = [], 0, time.time()
    for a in por:
        url = f"{base}/api/v2/addresses/{a}/transactions?filter=to"
        nxt, n = None, 0
        while True:
            d = get(url + ("&" + urllib.parse.urlencode(nxt) if nxt else ""))
            pages += 1
            items = d.get("items") or []
            stop = False
            for x in items:
                ts = calendar.timegm(time.strptime(x["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))
                if ts < t0:
                    stop = True
                    break
                if ts >= t1 or x.get("status") != "ok":
                    continue
                v = int(x.get("value") or 0) / 1e18
                if v <= 0:
                    continue
                n += 1
                frm = ((x.get("from") or {}).get("hash") or "").lower()
                rows.append({"perp": perp, "t": ts, "from": frm, "to": a, "amt": v, "share": v / circ, "tx": x.get("hash")})
            nxt = d.get("next_page_params")
            if stop or not nxt or not items:
                break
        print(f"  {a[:12]}: зачислений {n}, страниц всего {pages}, {time.time() - tt:.0f} с", flush=True)
    days = (t1 - t0) / 86400
    summ = {}
    for thr in (0.005, 0.0025, 0.001):
        ev, last = [], -10 ** 12
        for x in sorted(rows, key=lambda z: z["t"]):
            if x["share"] < thr or x["from"] in cex:
                continue
            if x["t"] - last >= GAP:
                ev.append(x)
            last = x["t"]
        summ[str(thr)] = {"events": len(ev), "per_month": round(len(ev) / days * 30.4, 1)}
    out = {"net": net, "perp": perp, "d0": d0, "d1": d1, "days": days, "n_rows": len(rows), "pages": pages,
           "summary": summ, "top": sorted([x for x in rows if x["from"] not in cex], key=lambda z: -z["share"])[:25]}
    out["recv"] = {}
    for x in rows:
        out["recv"][x["to"]] = out["recv"].get(x["to"], 0) + 1
    json.dump(out, open(f"s267/probe_{net}_{d0}.json", "w"), indent=0)
    print(f"{net} ({perp}, родная) {d0}…{d1} ({days:.0f} сут): зачислений на Binance {len(rows)}; ≥0,5% — "
          f"{summ['0.005']['events']} ({summ['0.005']['per_month']} в мес.); ≥0,25% — {summ['0.0025']['per_month']}; "
          f"≥0,1% — {summ['0.001']['per_month']} в мес.; страниц {pages}, {time.time() - tt:.0f} с", flush=True)


if __name__ == "__main__":
    main()
