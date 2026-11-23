"""s252 — состав индексной цены живых перпов Binance USDT-M: `www.binance.com/fapi/v1/constituents` для каждого
бессрочного контракта (PERPETUAL, TRADING, к USDT), не чаще 4 запросов в секунду. Спот Binance — `exchangeInfo` спота
(data-api.binance.vision), пара BASE/USDT, BASE/USDC, BASE/FDUSD в статусе TRADING (с учётом префиксов 1000/1000000).
Итог — /home/user/mc_data/s252/constituents.json: {символ: {"base", "onboard", "sub", "spot", "cons": [{exchange, symbol,
weight}]}}. Запуск: cd /home/user/mc_data/s252 && python3 -I <repo>/research/s252/study/constituents.py"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "research-script/1.0"}
URL = "https://www.binance.com/fapi/v1/constituents?symbol={}"


def base(asset):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", asset)
    if m and not m.group(2)[0].isdigit():
        return m.group(2)
    return asset


def get(url, tries=6):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code == 400:
                return {"error": 400}
            time.sleep(2 + 3 * i)
    return None


def main():
    fx = json.load(open("exinfo.json"))["symbols"]
    sp = json.load(open("spot_exinfo.json"))["symbols"]
    spot = {}
    for s in sp:
        if s["status"] == "TRADING" and s["quoteAsset"] in ("USDT", "USDC", "FDUSD", "TRY", "BTC", "BNB", "ETH", "EUR"):
            spot.setdefault(s["baseAsset"], []).append(s["symbol"])
    out = json.load(open("constituents.json")) if os.path.exists("constituents.json") else {}
    todo = [s for s in fx if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT"
            and s["status"] in ("TRADING", "PENDING_TRADING") and not out.get(s["symbol"], {}).get("ok")]
    print("к опросу:", len(todo), flush=True)
    for k, s in enumerate(todo):
        b = s["baseAsset"]
        r = get(URL.format(urllib.parse.quote(s["symbol"])))
        cons = [{"exchange": c.get("exchange"), "symbol": c.get("symbol"), "weight": float(c.get("weight") or 0)}
                for c in (r or {}).get("constituents") or []]
        out[s["symbol"]] = {"base": b, "coin": base(b), "onboard": s.get("onboardDate"),
                            "sub": s.get("underlyingSubType"), "utype": s.get("underlyingType"),
                            "spot": sorted(set(spot.get(b, []) + spot.get(base(b), []))),
                            "cons": cons, "ok": r is not None and "constituents" in (r or {})}
        if k % 50 == 0:
            json.dump(out, open("constituents.json", "w"))
            print(k, s["symbol"], [c["exchange"] for c in cons], flush=True)
        time.sleep(0.25)
    json.dump(out, open("constituents.json", "w"))
    print("готово:", len(out))


if __name__ == "__main__":
    main()
