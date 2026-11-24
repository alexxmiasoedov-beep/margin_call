"""s267 — проба частоты крупных заводов жетонов TON на Binance через toncenter v3 (без ключа, ≤ 1 запроса в секунду).

У Binance в сети TON у клиента свой адрес пополнения (`sameAddress: false` в getNetworkCoinAll), пополнения сметаются на
горячие кошельки. Адреса Binance — список TON из proof-of-reserves (`s250/por.json`) и кошельки с именем «Binance» у tonapi.io вне его
(EXTRA). Перевод жетона на адрес Binance
от адреса не из этого списка, сумма ≥ 0,5% монет в обращении (CMC сейчас), первое у монеты за 48 ч — событие. Для
картины — пороги 0,25% и 0,1%. Доходы не считаются.

Запуск из /home/user/mc_data: python3 -I <repo>/research/s267/study/ton_probe.py <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец>
Итог — /home/user/mc_data/s267/probe_TON_<начало>_<конец>.json и сводка на экран."""
import base64
import calendar
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://toncenter.com/api/v3/jetton/transfers"
UA = {"User-Agent": "research-script/1.0"}
GAP = 48 * 3600
JETTONS = {"NOT": 9, "DOGS": 9, "CATI": 9, "HMSTR": 9}   # десятичные знаки жетонов (стандарт TON — 9)
# Кошельки Binance вне списка proof-of-reserves (имя «Binance» у tonapi.io): 0:F99B… — сборщик пополнений 2024–2025 гг.,
# из него жетоны уходят на горячий кошелёк 0:CA1D… (Binance Hot Wallet). Без него внутренние переводы считались бы заводами.
EXTRA = ["0:F99B14600AE44D2F12B178E8C6EABD78892AE82C5E45B6898F9DEB7EB203F9C4"]


def raw(addr):
    """Адрес TON в виде «0:HEX» (из user-friendly base64url или уже сырого)."""
    if ":" in addr:
        w, h = addr.split(":")
        return f"{int(w)}:{h.upper()}"
    b = base64.urlsafe_b64decode(addr + "=" * (-len(addr) % 4))
    wc = b[1] if b[1] < 128 else b[1] - 256
    return f"{wc}:{b[2:34].hex().upper()}"


def get(params, tries=8):
    url = API + "?" + urllib.parse.urlencode(params, doseq=True)
    for k in range(tries):
        try:
            time.sleep(1.1)
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(3 + 3 * k)
                continue
            raise
        except Exception:  # noqa: BLE001
            time.sleep(3 + 3 * k)
    raise RuntimeError("toncenter: нет ответа")


def day(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%d"))


def main():
    d0, d1 = sys.argv[1:3]
    t0, t1 = day(d0), min(day(d1), int(time.time()))
    nets = json.load(open("/dev/shm/s267/nets.json"))
    por = [r["address"] for r in json.load(open("s250/por.json"))["data"] if r["network"] in ("TON", "TONMEMO")]
    binance = sorted({raw(a) for a in por} | set(EXTRA))
    rows = []
    for p, dec in JETTONS.items():
        r = nets[p]
        master = r["nets"]["TON"]["contract"]
        # листаем по времени (start_utime = время последнего перевода страницы), а не смещением: большие offset
        # toncenter не отдаёт; повторы на границе страниц отсекаем по хешу транзакции
        cur, n, seen = t0, 0, set()
        while cur < t1:
            w1 = min(t1, cur + 30 * 86400)   # запрос не шире 30 сут: на всём периоде сразу toncenter не отвечает
            d = get({"owner_address": binance, "direction": "in", "jetton_master": master, "start_utime": cur,
                     "end_utime": w1, "limit": 1000, "offset": 0, "sort": "asc"})
            tr = d.get("jetton_transfers") or []
            new = 0
            for x in tr:
                key = (x.get("transaction_hash"), x.get("source"), x.get("amount"))
                if key in seen:
                    continue
                seen.add(key)
                new += 1
                if x.get("transaction_aborted"):
                    continue
                amt = int(x["amount"]) / 10 ** dec
                rows.append({"perp": p, "t": x["transaction_now"], "from": raw(x["source"]), "to": raw(x["destination"]),
                             "amt": amt, "share": amt / r["circ"], "tx": x.get("transaction_hash")})
            n += new
            if len(tr) < 1000 or not new:
                cur = w1          # окно исчерпано — следующее
            else:
                cur = max(x["transaction_now"] for x in tr)
        print(f"{p}: переводов на Binance {n}", flush=True)
    bset = set(binance)
    days = (t1 - t0) / 86400
    out = {"d0": d0, "d1": d1, "days": days, "binance": binance, "n_rows": len(rows)}
    summ = {}
    for thr in (0.005, 0.0025, 0.001):
        ev, last = [], {}
        for r in sorted(rows, key=lambda z: z["t"]):
            if r["share"] < thr or r["from"] in bset:
                continue
            if r["t"] - last.get(r["perp"], -10 ** 12) >= GAP:
                ev.append(r)
            last[r["perp"]] = r["t"]
        summ[str(thr)] = {"events": len(ev), "per_month": round(len(ev) / days * 30.4, 1),
                          "by_perp": {p: sum(1 for e in ev if e["perp"] == p) for p in JETTONS}}
    out["summary"] = summ
    out["internal_big"] = sum(1 for r in rows if r["share"] >= 0.005 and r["from"] in bset)
    out["top"] = sorted([r for r in rows if r["from"] not in bset], key=lambda z: -z["share"])[:25]
    out["rows_big"] = [r for r in rows if r["share"] >= 0.0005]   # все переводы ≥ 0,05% — список событий для проверки
    out["recv"] = {}
    for r in rows:
        out["recv"][r["to"]] = out["recv"].get(r["to"], 0) + 1
    json.dump(out, open(f"s267/probe_TON_{d0}_{d1}.json", "w"), indent=0)
    print(f"TON {d0}…{d1} ({days:.0f} сут): переводов {len(rows)}; ≥0,5% — {summ['0.005']['events']} "
          f"({summ['0.005']['per_month']} в мес., {summ['0.005']['by_perp']}); ≥0,25% — {summ['0.0025']['per_month']}; "
          f"≥0,1% — {summ['0.001']['per_month']} в мес.; внутренних ≥0,5% {out['internal_big']}; получатели {out['recv']}",
          flush=True)


if __name__ == "__main__":
    main()
