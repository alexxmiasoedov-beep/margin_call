"""s267 — проба частоты крупных заводов APT на Binance через публичный индексатор Aptos Labs (GraphQL без ключа,
анонимный предел — не чаще запроса в 3 с; REST-узел хранит лишь последние ~150 млн версий).

У Binance в Aptos у клиента свой адрес пополнения (`sameAddress: false`), пополнения сметаются на горячие кошельки
из proof-of-reserves (`s250/por.json`, сеть APT). Берутся зачисления APT (`fungible_asset_activities`, тип Deposit,
монета 0x1::aptos_coin::AptosCoin или FA 0xa) на адреса Binance с суммой ≥ 0,1% обращения в окне; источник — списание
в той же транзакции. Событие — ≥ 0,5% обращения (CMC сейчас), отправитель не Binance, первое за 48 ч. Доходы не считаются.

Запуск из /home/user/mc_data: python3 -I <repo>/research/s267/study/apt_probe.py <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец>"""
import calendar
import json
import sys
import time
import urllib.error
import urllib.request

URL = "https://api.mainnet.aptoslabs.com/v1/graphql"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
GAP = 48 * 3600


def q(s, var=None, tries=8):
    body = json.dumps({"query": s, "variables": var or {}}).encode()
    for k in range(tries):
        time.sleep(3)
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=UA), timeout=90).read())
            if d.get("errors"):
                raise RuntimeError(str(d["errors"])[:300])
            return d["data"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504, 408):
                time.sleep(10 + 10 * k)
                continue
            raise
        except RuntimeError as e:
            if "Timed Out" in str(e) or "408" in str(e):
                time.sleep(10 + 5 * k)
                continue
            raise
        except Exception:  # noqa: BLE001
            time.sleep(10 + 5 * k)
    raise RuntimeError("Aptos: нет ответа")


DEP = """query($own: [String!], $t0: timestamp, $t1: timestamp, $min: numeric, $off: Int) {
  fungible_asset_activities(where: {owner_address: {_in: $own}, amount: {_gte: $min},
      transaction_timestamp: {_gte: $t0, _lt: $t1}, asset_type: {_in: ["0x1::aptos_coin::AptosCoin", "0xa"]},
      is_transaction_success: {_eq: true}, type: {_in: ["0x1::coin::DepositEvent", "0x1::fungible_asset::Deposit"]}},
    order_by: {transaction_version: asc}, limit: 100, offset: $off) {
    transaction_version transaction_timestamp owner_address amount type } }"""
SRC = """query($v: bigint) { fungible_asset_activities(where: {transaction_version: {_eq: $v},
    asset_type: {_in: ["0x1::aptos_coin::AptosCoin", "0xa"]}, type: {_in: ["0x1::coin::WithdrawEvent", "0x1::fungible_asset::Withdraw"]}}) {
    owner_address amount } }"""


def main():
    d0, d1 = sys.argv[1:3]
    nets = json.load(open("/dev/shm/s267/nets.json"))
    circ = nets["APT"]["circ"]
    por = sorted({r["address"] for r in json.load(open("s250/por.json"))["data"] if r["network"] == "APT"})
    rows, off = [], 0
    while True:
        d = q(DEP, {"own": por, "t0": d0 + "T00:00:00", "t1": d1 + "T00:00:00", "min": str(int(0.001 * circ * 1e8)), "off": off})
        a = d["fungible_asset_activities"]
        for x in a:
            amt = int(x["amount"]) / 1e8
            src = q(SRC, {"v": x["transaction_version"]})["fungible_asset_activities"]
            frm = [s["owner_address"] for s in src if int(s["amount"]) > 0]
            rows.append({"t": calendar.timegm(time.strptime(x["transaction_timestamp"][:19], "%Y-%m-%dT%H:%M:%S")),
                         "to": x["owner_address"], "from": frm[0] if frm else None,
                         "internal": bool(frm) and all(f in por for f in frm), "amt": amt, "share": amt / circ,
                         "v": x["transaction_version"]})
        print(f"  смещение {off}: {len(a)} зачислений", flush=True)
        if len(a) < 100:
            break
        off += 100
    days = (calendar.timegm(time.strptime(d1, "%Y-%m-%d")) - calendar.timegm(time.strptime(d0, "%Y-%m-%d"))) / 86400
    summ = {}
    for thr in (0.005, 0.0025, 0.001):
        ev, last = [], -10 ** 12
        for r in sorted(rows, key=lambda z: z["t"]):
            if r["share"] < thr or r["internal"]:
                continue
            if r["t"] - last >= GAP:
                ev.append(r)
            last = r["t"]
        summ[str(thr)] = {"events": len(ev), "per_month": round(len(ev) / days * 30.4, 1)}
    out = {"d0": d0, "d1": d1, "days": days, "rows": rows, "summary": summ}
    json.dump(out, open(f"s267/probe_APT_{d0}.json", "w"), indent=0)
    print(f"APT {d0}…{d1} ({days:.0f} сут): зачислений ≥0,1% {len(rows)} (внутренних {sum(r['internal'] for r in rows)}); "
          f"≥0,5% — {summ['0.005']['events']} ({summ['0.005']['per_month']} в мес.); ≥0,25% — {summ['0.0025']['per_month']}; "
          f"≥0,1% — {summ['0.001']['per_month']} в мес.", flush=True)


if __name__ == "__main__":
    main()
