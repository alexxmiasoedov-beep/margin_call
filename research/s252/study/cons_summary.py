"""s252 — сводка состава индекса у живых перпов USDT-M без спота Binance (constituents.json → печать и
/home/user/mc_data/s252/nospot.json). «Без спота» — в составе индекса нет площадки `binance` (спот Binance) и в exchangeInfo
спота нет пары с той же базой (с учётом 1000/1000000). Без индексов, предрынка и контрактов без состава.
Запуск: cd /home/user/mc_data/s252 && python3 -I <repo>/research/s252/study/cons_summary.py"""
import collections
import json
import time

import numpy as np

C = json.load(open("constituents.json"))
rows = {}
for s, v in C.items():
    if not v["ok"] or not v["cons"]:
        continue
    if "Index" in (v["sub"] or []) or "Pre-Market" in (v["sub"] or []):
        continue
    ex = [c["exchange"] for c in v["cons"]]
    if "binance" in ex or v["spot"]:
        continue
    rows[s] = v
print("живых перпов USDT-M (PERPETUAL) с составом индекса:", sum(1 for v in C.values() if v["ok"] and v["cons"]))
print("без спота Binance:", len(rows))
yr = collections.Counter(time.strftime("%Y", time.gmtime(v["onboard"] / 1000)) for v in rows.values())
print("год запуска перпа:", sorted(yr.items()))
alpha = sum(1 for v in rows.values() if "Alpha" in (v["sub"] or []))
print("с тегом Alpha в подтипе:", alpha)

n = collections.Counter()
w = collections.defaultdict(list)
for s, v in rows.items():
    for c in v["cons"]:
        n[c["exchange"]] += 1
        w[c["exchange"]].append(c["weight"])
print("\nплощадка | перпов | доля перпов | медиана веса | средний вес | сумма весов (доля всего индекса)")
tot = len(rows)
for e, k in n.most_common():
    print(f"{e:16s} {k:4d} {k / tot:6.1%} {np.median(w[e]):6.3f} {np.mean(w[e]):6.3f} {sum(w[e]) / tot:6.1%}")
# классы площадок
CEX = {"gateio", "mexc", "bitget", "bybit", "okex", "kucoin", "huobi", "htx", "coinbase", "kraken", "bingx", "lbank",
       "bitmart", "coinex", "upbit", "bithumb", "cryptocom", "xt"}
cls = collections.Counter()
share = collections.defaultdict(list)
for s, v in rows.items():
    g = collections.defaultdict(float)
    for c in v["cons"]:
        e = c["exchange"]
        k = ("binance_future" if e == "binance_future" else "binance_alpha" if e == "binance_alpha" else
             "dex" if ("swap" in e.lower() or "dex" in e.lower() or "uniswap" in e.lower() or "raydium" in e.lower()
                       or "orca" in e.lower() or "meteora" in e.lower() or "aerodrome" in e.lower()) else
             "cex" if e in CEX else "прочее:" + e)
        g[k] += c["weight"]
    for k in ("cex", "dex", "binance_alpha", "binance_future"):
        share[k].append(g.get(k, 0.0))
    cls[tuple(sorted(k for k in g if g[k] > 0))] += 1
print("\nсочетания классов площадок:")
for k, m in cls.most_common():
    print(f"  {m:4d}  {' + '.join(k)}")
print("\nвес классов в индексе (медиана / среднее / доля перпов с классом):")
for k, a in share.items():
    a = np.array(a)
    print(f"  {k:15s} медиана {np.median(a):.3f}  среднее {a.mean():.3f}  есть у {np.mean(a > 0):.0%}")
# DEX — какие и с какими парами
dex = collections.Counter()
for v in rows.values():
    for c in v["cons"]:
        e = c["exchange"]
        if e not in CEX and e not in ("binance_future", "binance_alpha"):
            pair = c["symbol"].split("/")[-1] if "/" in c["symbol"] else c["symbol"]
            dex[(e, pair.split("-")[0])] += 1
print("\nDEX-площадки (площадка, котируемая валюта пары):", dex.most_common(20))
json.dump(rows, open("nospot.json", "w"), ensure_ascii=False)
