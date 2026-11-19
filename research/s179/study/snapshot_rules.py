"""s179 — снимок действующих лимитов (19.11.2026): потолки фандинга и интервалы, ценовые коридоры перпов и спота Binance,
потолки OI Hyperliquid. Только текущее состояние — истории у этих полей нет.

Запуск: python3 -I snapshot_rules.py <папка данных>   (сохраняет JSON в <данные>/s179/raw/, если их там нет)
Источники без ключей:
  www.binance.com/fapi/v1/fundingInfo, www.binance.com/fapi/v1/exchangeInfo (fapi.binance.com из облака — 451),
  www.binance.com/api/v3/exchangeInfo, api.hyperliquid.xyz/info (perpsAtOpenInterestCap, metaAndAssetCtxs).
"""
import json
import os
import sys
import time
import urllib.request
from collections import Counter

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
RAW = os.path.join(D, "s179/raw")
os.makedirs(RAW, exist_ok=True)
UA = {"User-Agent": "research-script/1.0"}


def get(name, url, body=None):
    fn = os.path.join(RAW, name)
    if os.path.exists(fn):
        return json.load(open(fn))
    for i in range(3):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                         headers={**UA, **({"Content-Type": "application/json"} if body else {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            open(fn, "wb").write(data)
            return json.loads(data)
        except Exception as e:  # сеть ненадёжна — пауза и повтор
            print("ошибка", name, e)
            time.sleep(5 + 10 * i)
    return None


def main():
    fi = get("fapi_fundingInfo.json", "https://www.binance.com/fapi/v1/fundingInfo")
    ex = get("fapi_exchangeInfo.json", "https://www.binance.com/fapi/v1/exchangeInfo")
    sp = get("spot_exchangeInfo.json", "https://www.binance.com/api/v3/exchangeInfo")
    cap = get("hl_perpsAtOpenInterestCap.json", "https://api.hyperliquid.xyz/info", {"type": "perpsAtOpenInterestCap"})
    meta = get("hl_metaAndAssetCtxs.json", "https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"})
    if fi:
        usdt = [x for x in fi if x["symbol"].endswith("USDT")]
        c = Counter((x["adjustedFundingRateCap"].rstrip("0"), int(x["fundingIntervalHours"])) for x in usdt)
        print(f"fundingInfo: записей {len(fi)}, USDT {len(usdt)}; (потолок, интервал ч) → число: {c.most_common(12)}")
        if ex:
            st = {s["symbol"]: (s.get("contractType"), s.get("status")) for s in ex["symbols"]}
            cc = Counter((x["adjustedFundingRateCap"].rstrip("0"), int(x["fundingIntervalHours"])) for x in usdt
                         if st.get(x["symbol"]) == ("PERPETUAL", "TRADING"))
            print(f"  только криптоперпы в торговле (PERPETUAL, TRADING): {cc.most_common(12)}")
    if ex:
        perps = [s for s in ex["symbols"] if s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING"]
        pp = Counter(); tp = Counter(); mt = Counter()
        for s in perps:
            for f in s["filters"]:
                if f["filterType"] == "PERCENT_PRICE":
                    pp[(f["multiplierUp"], f["multiplierDown"])] += 1
            tp[s.get("triggerProtect")] += 1
            mt[s.get("marketTakeBound")] += 1
        types = Counter((s.get("contractType"), s.get("status")) for s in ex["symbols"])
        print(f"перпы Binance: {types.most_common()}")
        print(f"  коридор лимитных заявок к марк-цене (PERCENT_PRICE): {pp.most_common()}")
        print(f"  порог защиты цены стоп-заявок (triggerProtect): {tp.most_common()}")
        print(f"  коридор рыночных заявок (marketTakeBound): {mt.most_common()}")
    if sp:
        c = Counter()
        for s in sp["symbols"]:
            if s["status"] != "TRADING" or s["quoteAsset"] != "USDT":
                continue
            for f in s["filters"]:
                if f["filterType"] == "PERCENT_PRICE_BY_SIDE":
                    c[(f["bidMultiplierUp"], f["bidMultiplierDown"], f["askMultiplierUp"], f["askMultiplierDown"],
                       f["avgPriceMins"])] += 1
        print(f"спот Binance, пары к USDT: коридор (покупка вверх, покупка вниз, продажа вверх, продажа вниз, минут "
              f"средней): {c.most_common()}")
    if cap is not None and meta:
        u, ctx = meta
        live = {a["name"]: (a.get("isDelisted", False), c_) for a, c_ in zip(u["universe"], ctx)}
        print(f"Hyperliquid: перпов {len(u['universe'])}, на потолке OI сейчас {len(cap)}:")
        for n in cap:
            dl, c_ = live.get(n, (None, {}))
            print(f"  {n}: {'снят' if dl else 'торгуется'}, оборот за сутки {float(c_.get('dayNtlVlm') or 0):,.0f} $")


if __name__ == "__main__":
    main()
