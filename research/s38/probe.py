"""s38 — опись публичных данных Binance, BingX и Gate: какие запросы отвечают без ключа (из облака Binance открывается
через www.binance.com, fapi.binance.com и api.binance.com дают 451), какие поля и какая глубина истории.
Ничего не сохраняет, печатает сводку. Запуск: python3 probe.py"""
import datetime
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Accept": "application/json"}


def get(u, data=None):
    r = urllib.request.urlopen(urllib.request.Request(u, data=json.dumps(data).encode() if data is not None else None,
                                                      headers=UA), timeout=60)
    b = r.read()
    return len(b), json.loads(b)


def probe(name, u, data=None):
    try:
        n, j = get(u, data)
        d = j.get("data", j) if isinstance(j, dict) else j
        x = d[0] if isinstance(d, list) and d else d
        keys = sorted(x.keys())[:14] if isinstance(x, dict) else type(x).__name__
        print(f"  200 {name:38s} {n:9d} б  {keys}")
    except urllib.error.HTTPError as e:
        print(f"  {e.code} {name:38s} {e.read()[:100]!r}")
    except Exception as e:
        print(f"  ERR {name:38s} {str(e)[:100]}")
    time.sleep(0.25)


def s3_ls(prefix):
    U = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix="
    x = urllib.request.urlopen(U + urllib.parse.quote(prefix, safe="/"), timeout=60).read().decode()
    return [p.replace(prefix, "") for p in re.findall(r"<Prefix>([^<]+)</Prefix>", x)[1:]]


if __name__ == "__main__":
    print("Архив data.binance.vision:")
    for p in ("data/futures/um/daily/", "data/futures/um/monthly/", "data/futures/cm/daily/", "data/spot/daily/", "data/option/daily/"):
        print(f"  {p}: {s3_ls(p)}")
    W, S = "https://www.binance.com", "WIFUSDT"
    print("Binance REST (через www.binance.com):")
    for path, q in (("fapi/v1/exchangeInfo", ""), ("fapi/v1/depth", f"symbol={S}&limit=10"), ("fapi/v1/aggTrades", f"symbol={S}&limit=2"),
                    ("fapi/v1/klines", f"symbol={S}&interval=1h&limit=2"), ("fapi/v1/premiumIndexKlines", f"symbol={S}&interval=1h&limit=2"),
                    ("fapi/v1/premiumIndex", f"symbol={S}"), ("fapi/v1/fundingRate", f"symbol={S}&limit=2"), ("fapi/v1/fundingInfo", ""),
                    ("fapi/v1/openInterest", f"symbol={S}"), ("fapi/v1/constituents", f"symbol={S}"), ("fapi/v1/indexInfo", ""),
                    ("fapi/v1/insuranceBalance", ""), ("fapi/v1/assetIndex", ""),
                    ("futures/data/openInterestHist", f"symbol={S}&period=1h&limit=2"),
                    ("futures/data/topLongShortPositionRatio", f"symbol={S}&period=1h&limit=2"),
                    ("futures/data/globalLongShortAccountRatio", f"symbol={S}&period=1h&limit=2"),
                    ("futures/data/takerlongshortRatio", f"symbol={S}&period=1h&limit=2"),
                    ("futures/data/basis", f"pair={S}&contractType=PERPETUAL&period=1h&limit=2"),
                    ("api/v3/klines", f"symbol={S}&interval=1h&limit=2")):
        probe(path, f"{W}/{path}" + (f"?{q}" if q else ""))
    print("Binance, веб-API сайта (bapi):")
    probe("ставки маржи", f"{W}/bapi/margin/v1/public/margin/vip/spec/list-all")
    probe("справочник монет: теги, обращение", f"{W}/bapi/composite/v1/public/marketing/symbol/list")
    probe("список Alpha", f"{W}/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list")
    probe("все активы", f"{W}/bapi/asset/v2/public/asset/asset/get-all-asset")
    probe("копитрейдинг (портфели)", f"{W}/bapi/futures/v1/friendly/future/copy-trade/home-page/query-list",
          {"pageNumber": 1, "pageSize": 3, "timeRange": "30D", "dataType": "ROI", "favoriteOnly": False, "hideFull": False,
           "order": "DESC", "portfolioType": "PUBLIC"})
    probe("P2P USDT/TRY", "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
          {"fiat": "TRY", "page": 1, "rows": 3, "tradeType": "BUY", "asset": "USDT", "countries": [], "proMerchantAds": False,
           "publisherType": None, "payTypes": []})
    X = "https://open-api.bingx.com"
    print("BingX (open-api.bingx.com):")
    for path, q in (("/openApi/swap/v2/quote/contracts", ""), ("/openApi/swap/v2/quote/premiumIndex", "symbol=WIF-USDT"),
                    ("/openApi/swap/v2/quote/fundingRate", "symbol=WIF-USDT&limit=2"), ("/openApi/swap/v3/quote/klines", "symbol=WIF-USDT&interval=1h&limit=2"),
                    ("/openApi/swap/v2/quote/openInterest", "symbol=WIF-USDT"), ("/openApi/swap/v2/quote/depth", "symbol=WIF-USDT&limit=5"),
                    ("/openApi/swap/v2/quote/trades", "symbol=WIF-USDT&limit=2"), ("/openApi/swap/v1/market/markPriceKlines", "symbol=WIF-USDT&interval=1h&limit=2")):
        probe(path, X + path + (f"?{q}" if q else ""))
    print("Gate (api.gateio.ws):")
    probe("futures/usdt/contract_stats", "https://api.gateio.ws/api/v4/futures/usdt/contract_stats?contract=WIF_USDT&interval=1h&limit=2")
    now = int(time.time())
    for days in (170, 190):
        try:
            n, y = get(f"https://api.gateio.ws/api/v4/futures/usdt/contract_stats?contract=WIF_USDT&interval=1h&limit=2&from={now - days * 86400}")
            print(f"  Gate contract_stats {days} сут назад: {len(y)} точек")
        except urllib.error.HTTPError as e:
            print(f"  Gate contract_stats {days} сут назад: {e.code} {e.read()[:80]!r}")
