#!/usr/bin/env python3
"""s209: частота «нетто-продажи богатых» на Bithumb за 7 сут снимка (для оценки частоты гипотезы Г3).

Берёт investList (нетто-покупка «богатых» клиентов, вон, по суткам KST) из снимка bithumb_indicators.py и
дневной оборот монеты на Bithumb за те же сутки (публичные свечи api.bithumb.com/v1/candles/days,
candle_acc_trade_price; сутки свечи Bithumb — по KST, как и standardDate). Считает долю нетто-потока
«богатых» в обороте дня и сколько монето-суток проходят пороги. Доходы и цены после дня не считаются.
"""
import glob, gzip, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common209 import jget

snap = json.load(gzip.open(sorted(glob.glob("/home/user/mc_data/s209/bithumb/snap_*.json.gz"))[-1], "rt"))
rows = []
for ct, d in snap["coins"].items():
    w = d.get("wealthy") or {}
    inv = w.get("investList") or []
    if not inv:
        continue
    c, j = jget("https://api.bithumb.com/v1/candles/days", {"market": "KRW-" + d["symbol"], "count": 10}, gap=0.12)
    if c != 200 or not isinstance(j, list):
        continue
    turn = {x["candle_date_time_kst"][:10]: float(x["candle_acc_trade_price"]) for x in j}
    for x in inv:
        t = turn.get(x["standardDate"])
        if t and t > 0:
            rows.append((d["symbol"], x["standardDate"], float(x["tradeAmount"]), t))
print("монето-суток с оборотом:", len(rows), "монет:", len({r[0] for r in rows}),
      "дни:", min(r[1] for r in rows), "…", max(r[1] for r in rows))
sh = [r[2] / r[3] for r in rows]
print("нетто «богатых» / оборот дня: медиана %.3f, p10 %.3f, p90 %.3f, доля дней с продажей %.0f%%" % (
    statistics.median(sh), sorted(sh)[len(sh) // 10], sorted(sh)[9 * len(sh) // 10], 100 * sum(1 for x in sh if x < 0) / len(sh)))
days = len({r[1] for r in rows})
for thr in (0.05, 0.10, 0.20):
    k = sum(1 for x in sh if x <= -thr)
    k2 = sum(1 for r, x in zip(rows, sh) if x <= -thr and r[3] >= 1e9)
    print(f"  продажа «богатых» ≥ {thr:.0%} оборота: {k} монето-суток за {days} сут ({k/days*30.44:.0f} в мес.), "
          f"из них при обороте ≥ 1 млрд вон: {k2} ({k2/days*30.44:.0f} в мес.)")
