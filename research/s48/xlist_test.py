"""s48 — запуск USDT-фьючерса монеты на OKX, Gate, KuCoin или Bitget, когда фьючерс Binance торгуется ≥ суток (гипотеза —
ВЫВОДЫ.md, записана до расчёта). Время запуска — из публичных списков фьючерсов (сохраняются в s48/lists.json). Шорт
фьючерса Binance с закрытия первой 15-мин свечи после запуска: основной — 30 сут без тейка, стоп +50% (как 🅱️); ещё 7 сут
со стопом +50% и S_7_20. Одно событие на монету за 7 сут. Плацебо — та же монета за 45/90/135 сут.
Запуск из папки с данными."""
import json
import os
import re
import sys
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EXITS = {"S_30d": dict(tp=None, sl=0.50, hold_h=720), "S_7d": dict(tp=None, sl=0.50, hold_h=168),
         "S_7_20": dict(tp=0.07, sl=0.20, hold_h=48)}


def get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())


def lists():
    path = "s48/lists.json"
    if os.path.exists(path):
        return json.load(open(path))
    out = []
    for i in get("https://www.okx.com/api/v5/public/instruments?instType=SWAP")["data"]:
        if i.get("settleCcy") == "USDT" and i.get("listTime"):
            out.append(("OKX", i["instId"].split("-")[0], int(i["listTime"]) / 1000))
    for i in get("https://api.gateio.ws/api/v4/futures/usdt/contracts"):
        t = i.get("launch_time") or i.get("create_time")
        if t:
            out.append(("Gate", i["name"].split("_")[0], float(t)))
    for i in get("https://api-futures.kucoin.com/api/v1/contracts/active")["data"]:
        if i.get("quoteCurrency") == "USDT" and i.get("firstOpenDate") and i.get("type") == "FFWCSX":
            b = i["baseCurrency"]; b = "BTC" if b == "XBT" else b
            out.append(("KuCoin", b, int(i["firstOpenDate"]) / 1000))
    for i in get("https://api.bitget.com/api/v2/mix/market/contracts?productType=USDT-FUTURES")["data"]:
        if i.get("launchTime") and str(i["launchTime"]).isdigit() and int(i["launchTime"]) > 0:
            out.append(("Bitget", i["baseCoin"], int(i["launchTime"]) / 1000))
    os.makedirs("s48", exist_ok=True)
    json.dump(out, open(path, "w"))
    return out


def main():
    L = lists()
    print("запусков в списках:", {ex: sum(1 for x in L if x[0] == ex) for ex in ("OKX", "Gate", "KuCoin", "Bitget")})
    ev = []
    for ex, base, ts in L:
        base = re.sub(r"^(1000000|1000)", "", base)
        s, _ = fut_of(base)
        if not s or s not in K:
            continue
        lo, hi = live(s)
        if ts < lo + DAY or ts > hi or ts < pd.Timestamp("2024-10-02", tz="UTC").timestamp():
            continue
        ev.append((ts, s, ex))
    ev.sort()
    rows, last = [], {}
    for ts, s, ex in ev:
        if ts - last.get(s, -1e18) < 7 * DAY:
            continue
        i = idx_at(s, ts)
        if i is None:
            continue
        last[s] = ts
        d = dict(s=s, t=ts, ex=ex)
        for nm, kw in EXITS.items():
            x = trade(s, i + 1, side=-1, **kw)
            d[nm] = x["net"] if x else np.nan
            p = []
            for dd in (45, 90, 135):
                j = idx_at(s, ts - dd * DAY)
                if j is not None:
                    y = trade(s, j + 1, side=-1, **kw)
                    if y:
                        p.append(y["net"])
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s48/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий: {len(X)} ({len(X) / months:.1f} в месяц), монет {X.s.nunique()}; по биржам {X.ex.value_counts().to_dict()}")

    def line(lab, x, col):
        x = x[x[col].notna()]
        if len(x) < 8:
            return f"  {lab:22s} {col:7s} мало ({len(x)})"
        m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
        h1, h2 = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
        return (f"  {lab:22s} {col:7s} n={n:4d} {m:+7.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} | половины"
                f" {h1:+7.2%} / {h2:+7.2%} | плацебо {x['pl_' + col].mean():+7.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    for col in EXITS:
        print(line("все", X, col))
    for ex in ("OKX", "Gate", "KuCoin", "Bitget"):
        print(line(ex, X[X.ex == ex], "S_30d"))


if __name__ == "__main__":
    main()
