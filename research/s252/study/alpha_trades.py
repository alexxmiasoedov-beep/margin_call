"""s252 — рынок Binance Alpha (площадка `binance_alpha` в индексе): открытые эндпоинты без ключа
`www.binance.com/bapi/defi/v1/public/alpha-trade/agg-trades` (история с первой сделки, fromId / startTime / endTime,
до 1000 сделок) и `…/alpha-trade/klines`. Поле m у всех сделок false — направление не размечено (нужно правило тика).
Пилот частоты крупных сделок: токены группы H с `binance_alpha` в индексе, по 2 случайных дня 2026 г. (зерно 252),
сделки за сутки (до 40 страниц), доля сделок ≥ 0,1 / 0,25 / 0,5% капитализации в обращении (CMC, день до сделки) и
сколько из них — продажи по правилу тика (цена сделки ниже предыдущей). Только частоты, без цены после событий.
Итог — /home/user/mc_data/s252/alpha_trades.json. Запуск: cd /home/user/mc_data && [S252_SEED=253] python3 -I <repo>/research/s252/study/alpha_trades.py
(S252_SEED ≠ 252 — вторая выборка из всех токенов Alpha в BNB Chain с binance_alpha в индексе, итог alpha_trades_<seed>.json)"""
import bisect
import json
import random
import time
import urllib.request

UA = {"User-Agent": "research-script/1.0"}
URL = "https://www.binance.com/bapi/defi/v1/public/alpha-trade/agg-trades?symbol={}USDT&startTime={}&endTime={}&limit=1000"
URL2 = "https://www.binance.com/bapi/defi/v1/public/alpha-trade/agg-trades?symbol={}USDT&fromId={}&limit=1000"


def get(url):
    for i in range(5):
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())
            time.sleep(0.3)
            return d.get("data") or []
        except Exception:  # noqa: BLE001
            time.sleep(3 + 3 * i)
    return None


def main():
    TK = json.load(open("s252/tokens.json"))
    TB = json.load(open("s252/bsc_tokens.json"))
    NS = json.load(open("s252/nospot.json"))
    import os
    seed = int(os.environ.get("S252_SEED", "252"))        # вторая выборка: S252_SEED=253, без ограничения группой H
    rng = random.Random(seed)
    out = {}
    cand = []
    for s, v in sorted(TB.items()):
        t = TK[s]
        if t.get("alpha_chain") != "bsc" or not t["bsc_native"] or not v.get("days") or not t.get("alpha_id"):
            continue
        if seed == 252 and (not v["bsc_supply"] or v["bsc_supply"] < 0.5 * v["days"][-1][1]):
            continue
        if not any(c["exchange"] == "binance_alpha" for c in NS[s]["cons"]):
            continue
        cand.append(s)
    pick = sorted(rng.sample(cand, min(12, len(cand))))
    for s in pick:
        v, t = TB[s], TK[s]
        D = [d[0] for d in v["days"]]
        days = sorted(rng.sample(range(1767225600, 1794700800, 86400), 2))     # 01.01.2026 – 15.11.2026
        res = []
        for d0 in days:
            i = bisect.bisect_right(D, time.strftime("%Y-%m-%d", time.gmtime(d0 - 86400))) - 1
            if i < 0:
                continue
            mcap = v["days"][i][1] * v["days"][i][2]
            tr = get(URL.format(t["alpha_id"], d0 * 1000, (d0 + 86400) * 1000 - 1))
            if tr is None:
                continue
            end = (d0 + 86400) * 1000
            allt, pages, last = [x for x in tr if x["T"] < end], 1, tr[-1] if tr else None
            while last and len(tr) == 1000 and pages < 40 and last["T"] < end:
                tr = get(URL2.format(t["alpha_id"], last["a"] + 1))
                if not tr:
                    break
                allt += [x for x in tr if x["T"] < end]
                last, pages = tr[-1], pages + 1
            n = len(allt)
            usd = [float(x["p"]) * float(x["q"]) for x in allt]
            sell = [k > 0 and float(allt[k]["p"]) < float(allt[k - 1]["p"]) for k in range(n)]
            row = {"day": time.strftime("%Y-%m-%d", time.gmtime(d0)), "mcap": mcap, "trades": n, "pages": pages,
                   "complete": not (last and last["T"] < end and len(tr or []) == 1000), "vol": sum(usd)}
            for thr in (0.001, 0.0025, 0.005):
                big = [k for k in range(n) if usd[k] >= thr * mcap]
                row[f"n{thr}"] = len(big)
                row[f"s{thr}"] = sum(1 for k in big if sell[k])
            res.append(row)
            print(s, row, flush=True)
        out[s] = res
    json.dump(out, open("s252/alpha_trades.json" if seed == 252 else f"s252/alpha_trades_{seed}.json", "w"), indent=0)


if __name__ == "__main__":
    main()
