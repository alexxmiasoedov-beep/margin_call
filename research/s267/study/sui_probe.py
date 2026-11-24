"""s267 — проба частоты крупных заводов токенов Sui на Binance через Sui GraphQL (без ключа, история с генезиса).

У Binance в сети Sui у клиента свой адрес пополнения (`sameAddress: false`), пополнения сметаются на горячий кошелёк
(до 29.10.2026 — 0x935029…, после смены адресов — 0x8b38f6…; оба в proof-of-reserves). Скрипт листает все транзакции,
затронувшие адреса Binance из proof-of-reserves (`s250/por.json`, сеть SUI) в окне контрольных точек, и берёт изменения
баланса: плюс у адреса Binance по монете перпа (тип монеты — из сетей ввода Binance), минус у адреса не из списка Binance —
это сметание с адреса пополнения клиента. Зачисление без списания у адреса (вывод из стейкинга и т. п.) —
внутреннее. Событие — сумма ≥ 0,5% монет в обращении (CMC сейчас), первое у монеты за 48 ч;
для картины — пороги 0,25% и 0,1%. Доходы не считаются.

Запуск из /home/user/mc_data: python3 -I <repo>/research/s267/study/sui_probe.py <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец> [адреса через запятую]
Итог — /home/user/mc_data/s267/probe_SUI_<начало>.json и сводка на экран."""
import calendar
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sui_gql as G  # noqa: E402

GAP = 48 * 3600


def main():
    d0, d1 = sys.argv[1:3]
    nets = json.load(open("/dev/shm/s267/nets.json"))
    por = sorted({r["address"] for r in json.load(open("s250/por.json"))["data"] if r["network"] == "SUI"})
    scan = sys.argv[3].split(",") if len(sys.argv) > 3 else por
    coins = {}
    for b, r in nets.items():
        v = r["nets"].get("SUI")
        if v and v["contract"] and not r["skip"] and r.get("circ"):
            ct = v["contract"]
            if ct == "0x2::sui::SUI":
                ct = "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI"
            coins[ct] = {"perp": b, "circ": r["circ"]}
    dec = {"SUI": 9, "CETUS": 9, "WAL": 9, "MMT": 9, "HAEDAL": 9}
    cp0, cp1 = G.checkpoint_at(d0), G.checkpoint_at(min(calendar.timegm(time.strptime(d1, "%Y-%m-%d")), int(time.time()) - 60))
    print(f"Sui {d0}…{d1}: контрольные точки {cp0}–{cp1}; монет {len(coins)}: {[c['perp'] for c in coins.values()]}", flush=True)
    rows, seen, ntx = [], set(), {}
    t = time.time()
    for a in scan:
        n = 0
        for x in G.txs(a, cp0 - 1, cp1 + 1):
            n += 1
            if x["digest"] in seen:
                continue
            seen.add(x["digest"])
            eff = x["effects"]
            ts = calendar.timegm(time.strptime(eff["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))
            bcs = eff["balanceChanges"]["nodes"]
            for bc in bcs:
                own = (bc.get("owner") or {}).get("address")
                ct = bc["coinType"]["repr"]
                if own not in por or ct not in coins or int(bc["amount"]) <= 0:
                    continue
                c = coins[ct]
                amt = int(bc["amount"]) / 10 ** dec.get(c["perp"], 9)
                src = [(bb.get("owner") or {}).get("address") for bb in bcs
                       if bb["coinType"]["repr"] == ct and int(bb["amount"]) < 0]
                rows.append({"perp": c["perp"], "t": ts, "to": own, "from": src[0] if src else None,
                             "internal": not src or all(s in por for s in src), "amt": amt, "share": amt / c["circ"],
                             "tx": x["digest"], "sender": (x.get("sender") or {}).get("address")})
        ntx[a] = n
        print(f"  {a[:14]}: транзакций {n}, {round(time.time() - t)} с, запросов {G.STAT['req']}", flush=True)
    days = (min(calendar.timegm(time.strptime(d1, "%Y-%m-%d")), time.time()) - calendar.timegm(time.strptime(d0, "%Y-%m-%d"))) / 86400
    out = {"d0": d0, "d1": d1, "days": days, "cp": [cp0, cp1], "ntx": ntx, "coins": coins, "n_rows": len(rows)}
    summ = {}
    for thr in (0.005, 0.0025, 0.001):
        ev, last = [], {}
        for r in sorted(rows, key=lambda z: z["t"]):
            if r["share"] < thr or r["internal"]:
                continue
            if r["t"] - last.get(r["perp"], -10 ** 12) >= GAP:
                ev.append(r)
            last[r["perp"]] = r["t"]
        summ[str(thr)] = {"events": len(ev), "per_month": round(len(ev) / days * 30.4, 1),
                          "by_perp": {p: sum(1 for e in ev if e["perp"] == p) for p in sorted({e["perp"] for e in ev})}}
    out["summary"] = summ
    out["internal_big"] = sum(1 for r in rows if r["share"] >= 0.005 and r["internal"])
    out["top"] = sorted([r for r in rows if not r["internal"]], key=lambda z: -z["share"])[:30]
    out["rows_big"] = [r for r in rows if r["share"] >= 0.0005]   # все переводы ≥ 0,05% — для пересчёта порогов
    json.dump(out, open(f"s267/probe_SUI_{d0}.json", "w"), indent=0)
    print(f"SUI {d0}…{d1} ({days:.0f} сут): переводов {len(rows)}; ≥0,5% — {summ['0.005']['events']} "
          f"({summ['0.005']['per_month']} в мес., {summ['0.005']['by_perp']}); ≥0,25% — {summ['0.0025']['per_month']}; "
          f"≥0,1% — {summ['0.001']['per_month']} в мес.; внутренних ≥0,5% {out['internal_big']}; запросов {G.STAT['req']}",
          flush=True)


if __name__ == "__main__":
    main()
