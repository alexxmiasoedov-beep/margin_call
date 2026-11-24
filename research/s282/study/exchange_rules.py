"""s282 — ограничения Binance USDT-M для лимиток вдали от цены по публичному exchangeInfo и premiumIndex
(www.binance.com/fapi/v1/…, без ключа; fapi.binance.com из облака отвечает 451).

Сводка — /home/user/mc_data/s282/exchange_rules.txt (снимок 24.11.2026).
Запуск: python3 -I <repo>/research/s282/study/exchange_rules.py /dev/shm/s282/raw/exinfo.json /dev/shm/s282/raw/premium.json"""
import collections
import json
import sys

import numpy as np

OUT = "/home/user/mc_data/s282/exchange_rules.txt"


def main(f_ex, f_pr):
    d = json.load(open(f_ex))
    mark = {x["symbol"]: float(x["markPrice"]) for x in json.load(open(f_pr)) if float(x.get("markPrice") or 0) > 0}
    S = [x for x in d["symbols"] if x["contractType"] == "PERPETUAL" and x.get("underlyingType") == "COIN"
         and x["status"] == "TRADING" and x["quoteAsset"] == "USDT"]
    L = [f"Снимок exchangeInfo: всего символов {len(d['symbols'])}; криптоперпов USDT в торговле {len(S)}",
         f"Лимиты частоты (на аккаунт или IP): {d['rateLimits']}"]

    def filt(x, ft):
        return next((f for f in x["filters"] if f["filterType"] == ft), {})

    def dist(name, vals, top=8):
        c = collections.Counter(vals)
        L.append(f"{name}: " + "; ".join(f"{k} — {v}" for k, v in c.most_common(top)))

    pp = [(filt(x, "PERCENT_PRICE").get("multiplierUp"), filt(x, "PERCENT_PRICE").get("multiplierDown")) for x in S]
    dist("PERCENT_PRICE (вверх, вниз) от марк-цены", pp)
    dist("marketTakeBound (защита рыночной заявки, доля от марк-цены)", [x.get("marketTakeBound") for x in S])
    dist("triggerProtect (порог защиты стоп-заявок, |последняя − марк| / марк)", [x.get("triggerProtect") for x in S])
    dist("liquidationFee (сбор при ликвидации)", [x.get("liquidationFee") for x in S])
    dist("MIN_NOTIONAL ($)", [filt(x, "MIN_NOTIONAL").get("notional") for x in S])
    dist("MAX_NUM_ORDERS", [filt(x, "MAX_NUM_ORDERS").get("limit") for x in S])
    dist("maxMoveOrderLimit", [x.get("maxMoveOrderLimit") for x in S])
    dist("maintMarginPercent / requiredMarginPercent", [(x["maintMarginPercent"], x["requiredMarginPercent"]) for x in S])
    dist("permissionSets", [tuple(x.get("permissionSets", [])) for x in S])
    dist("timeInForce", [tuple(x.get("timeInForce", [])) for x in S])
    dist("orderTypes", [tuple(x.get("orderTypes", [])) for x in S], top=3)
    dist("POSITION_RISK_CONTROL", [filt(x, "POSITION_RISK_CONTROL").get("positionControlSide") for x in S])
    rel = []
    for x in S:
        m = mark.get(x["symbol"])
        mp = float(filt(x, "PRICE_FILTER").get("minPrice") or 0)
        tick = float(filt(x, "PRICE_FILTER").get("tickSize") or 0)
        if m:
            rel.append((mp / m, tick / m))
    rel = np.array(rel)
    q = np.quantile(rel[:, 0], [0.1, 0.5, 0.9, 0.99])
    L.append(f"PRICE_FILTER minPrice / марк-цена (как низко можно поставить покупку): 10/50/90/99-й перцентиль "
             + ", ".join(f"{v:.4f}" for v in q) + f"; выше 0,5 марка — {np.mean(rel[:, 0] > 0.5):.1%}")
    q = np.quantile(rel[:, 1], [0.1, 0.5, 0.9, 0.99])
    L.append("шаг цены / марк-цена (тик в долях цены): 10/50/90/99-й перцентиль " + ", ".join(f"{100 * v:.4f}%" for v in q)
             + f"; тик ≥ 0,1% цены — {np.mean(rel[:, 1] >= 0.001):.1%}")
    open(OUT, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:3])
