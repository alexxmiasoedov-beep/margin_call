#!/usr/bin/env python3
"""s209: снимок внутренних показателей Bithumb по монетам (страница монеты «거래소 정보» и «마켓 가이드»).

Ключи — чанки www.bithumb.com/react (кэш s204: /home/user/mc_data/s204/web/bithumb_site/chunks):
  jlf-YTXx.chunk.js  — блок «빗썸 내부 유통량»: /v1/trade/accumulation/deposit/{coin}-{mkt},
                        /v1/trade/purity/deposit/{coin}-{mkt}, /v1/trade/holders/{coin},
                        /v1/trade/top/holder/share/{coin}, /v1/trade/top/trader/share/{coin},
                        v1/trade/indicator/wealthy/stat?coinType= (7 сут «богатых»);
  DOttYLqf.chunk.js  — займ монет под продажу («하락에 투자», 2025-11): /v1/lending/downturn/disclosure/*;
  Do0p4fwl2.chunk.js — «마켓 가이드» на HOST_PUBLIC_INFO (gw.bithumb.com/public-info).
Хост: https://gw.bithumb.com/exchange (и /public-info). Без ключа; монета — код coinType (C0101 = BTC).

Значения (подписи интерфейса):
  accumulationDepositAmt — «빗썸 내부 유통량», монет на Bithumb (обновление раз в 10 мин);
  depositChangeRate      — «전일대비 유통량», % к 00:00 KST прошлых суток;
  purityDeposit          — «순입금(24H)», ввод (завершённый и ожидающий) минус вывод за 24 ч, в монетах;
  numberOfHolders        — «보유자», держателей на Bithumb;
  holdingPercentage      — «보유비중», доля 10 крупнейших держателей;
  tradingPercentage      — «거래비중», доля 10 крупнейших трейдеров в обороте (основа флага C);
  wealthy/stat           — holdPercentList (доля «богатых» в держателях монеты?, 7 сут), investList
                           (нетто-покупка «богатых», вон, 7 сут), buySellState.buyPercent (час).
Пишет /home/user/mc_data/s209/bithumb/snap_<UTC>.json.gz и сводку в stdout.
"""
import gzip, json, os, sys, time
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common209 import jget, perp_bases

EX = "https://gw.bithumb.com/exchange"
PI = "https://gw.bithumb.com/public-info"
OUT = "/home/user/mc_data/s209/bithumb"
GAP = 0.25


def main():
    os.makedirs(OUT, exist_ok=True)
    perps = perp_bases()
    c, intro = jget(EX + "/v1/comn/intro")
    coins = intro["data"]["coinList"]
    mkts = intro["data"].get("coinsOnMarketList") or {}
    krw = [x for x in coins if x.get("isLive") and x.get("siseCrncCd") == "C0100"]
    sel = [x for x in krw if x["coinSymbol"] in perps]
    print("монет Bithumb (живых, KRW):", len(krw), "с перпом Binance:", len(sel), flush=True)
    snap = {"utc": datetime.now(timezone.utc).isoformat(), "coins": {}, "global": {}}
    for path, params in [("/v1/lending/downturn/disclosure/assets-status", None),
                         ("/v1/lending/downturn/disclosure/auto-repayment/stats", None),
                         ("/v1/lending/downturn/aggregation/valuation", None),
                         ("/v1/lending/downturn/disclosure/policy/basic", None),
                         ("/v1/lending/downturn/available-coins", None),
                         ("/v1/credit-lending/available-coins/history", None)]:
        snap["global"][path] = jget(EX + path, params, gap=GAP)[1]
    for path, params in [("/v1/market-guide/wealthy/net-buying", {"count": 100}),
                         ("/v1/market-guide/wealthy/hold", {"count": 100}),
                         ("/v1/market-guide/top-bought-coin/amount", None),
                         ("/v1/market-guide/top-bought-coin/quantity", None),
                         ("/v1/market-guide/popular-searching-coin/C0100", None)]:
        snap["global"][path] = jget(PI + path, params, gap=GAP)[1]
    t0 = time.time()
    for i, x in enumerate(sel):
        ct, sym = x["coinType"], x["coinSymbol"]
        d = {"symbol": sym}
        for k, path in [("supply", f"/v1/trade/accumulation/deposit/{ct}-C0100"),
                        ("netdep", f"/v1/trade/purity/deposit/{ct}-C0100"),
                        ("holders", f"/v1/trade/holders/{ct}"),
                        ("top_hold", f"/v1/trade/top/holder/share/{ct}"),
                        ("top_trade", f"/v1/trade/top/trader/share/{ct}")]:
            c, j = jget(EX + path, gap=GAP)
            d[k] = j.get("data") if isinstance(j, dict) else {"err": c}
        c, j = jget(EX + "/v1/trade/indicator/wealthy/stat", {"coinType": ct}, gap=GAP)
        d["wealthy"] = j.get("data") if isinstance(j, dict) else {"err": c}
        snap["coins"][ct] = d
        if i % 50 == 0:
            print(f"{i+1}/{len(sel)} {sym} {time.time()-t0:.0f} с", flush=True)
    fn = f"{OUT}/snap_{datetime.now(timezone.utc):%Y%m%dT%H%M}.json.gz"
    with gzip.open(fn, "wt") as f:
        json.dump(snap, f, ensure_ascii=False)
    # сводка
    ok = lambda v: v not in (None, "", "-", "0")
    cnt = {k: sum(1 for d in snap["coins"].values() if isinstance(d.get(k), dict) and any(
        ok(v) for kk, v in d[k].items() if kk not in ("coinType", "mktType", "timestamp", "serverTime")))
        for k in ("supply", "netdep", "holders", "top_hold", "top_trade")}
    w7 = sum(1 for d in snap["coins"].values() if isinstance(d.get("wealthy"), dict)
             and (d["wealthy"].get("holdPercentList") or d["wealthy"].get("investList")))
    print("заполнено по монетам:", cnt, "wealthy/stat с рядом:", w7, flush=True)
    ex = snap["coins"].get("C0565")
    if ex:
        print("пример DOGE:", json.dumps(ex, ensure_ascii=False)[:900], flush=True)
    lend = snap["global"]["/v1/lending/downturn/disclosure/assets-status"]
    items = (lend.get("data") or {}).get("items") or []
    print("займ под продажу (assets-status): монет", len(items), "время", (lend.get("data") or {}).get("baseDateTime"),
          flush=True)
    print("файл", fn, os.path.getsize(fn), "байт", flush=True)


if __name__ == "__main__":
    main()
