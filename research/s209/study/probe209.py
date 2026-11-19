#!/usr/bin/env python3
"""s209: сводная проба найденных внутренних эндпоинтов — код ответа, глубина истории, пример ответа.

По одному-два запроса на эндпоинт (UA research-script/1.0, без ключей и куки). Примеры ответов —
/home/user/mc_data/s209/examples/<имя>.json. Журнал — probe209.log (запуск: python3 -I probe209.py > probe209.log).
"""
import json, os, sys, time
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common209 import fetch

EX = "/home/user/mc_data/s209/examples"
os.makedirs(EX, exist_ok=True)
NOW = int(time.time())


def ms(t):
    return datetime.fromtimestamp(int(t) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")


def rng_list(L, key, unit="ms"):
    try:
        if unit == "iso":
            v = sorted(x[key] for x in L)
            return f"{len(v)} точек, {v[0]} … {v[-1]}"
        v = [int(float(x[key] if isinstance(x, dict) else x[key])) for x in L]
        if unit == "s":
            v = [t * 1000 for t in v]
        return f"{len(v)} точек, {ms(min(v))} … {ms(max(v))}"
    except Exception as e:
        return f"{len(L)} строк ({e})"


P = []  # (имя, метод, url, тело, функция-описание)


def add(name, url, desc=None, method="GET", body=None):
    P.append((name, method, url, body, desc))


# --- Корея: Upbit
add("upbit_premium_days", "https://crix-api-cdn.upbit.com/v1/crix/price_difference/premium_records"
    "?code=CRIX.UPBIT.KRW-DOGE&timeUnit=DAYS_1&count=200&to=2024-11-20T00:00:00",
    lambda j: rng_list(j["records"], "recordTime", "iso"))
add("upbit_premium_hours", "https://crix-api-cdn.upbit.com/v1/crix/price_difference/premium_records"
    "?code=CRIX.UPBIT.KRW-DOGE&timeUnit=MINUTES_60&count=200&to=2024-06-28T00:00:00",
    lambda j: rng_list(j["records"], "recordTime", "iso"))
add("upbit_market_event_records", "https://crix-api-cdn.upbit.com/v1/crix/market-event-records"
    "?quoteCurrencyCode=KRW&start=2026-03-20%2000:00:00&end=2026-04-01%2000:00:00&page=1&size=5",
    lambda j: f"всего {j.get('totalCount')} записей в окне (история с 23.03.2026, s204)")
add("upbit_volume_power", "https://crix-api-cdn.upbit.com/v1/crix/trends/daily_volume_power"
    "?quoteCurrencyCode=KRW&orderBy=desc&count=500", lambda j: f"снимок, рынков {len(j['markets'])}")
add("upbit_interval_change_rate", "https://crix-api-cdn.upbit.com/v1/crix/trends/interval_change_rate",
    lambda j: f"снимок, рынков {len(j)}")
add("upbit_lending_budgets", "https://ccx-public.upbit.com/lending/public-api/v1/disclosures/budgets",
    lambda j: f"снимок {j.get('base_time')}, монет {j.get('contents_size')}")
add("upbit_lending_autorepay", "https://ccx-public.upbit.com/lending/public-api/v1/disclosures/auto-repayments"
    "?year=2025&month=9", lambda j: f"месяц {j.get('base_time')}, монет {j.get('contents_size')} (с 09.2025)")
add("upbit_daily_asset", "https://ucs.upbit.com/market/api/v1/disclosures/daily-asset",
    lambda j: f"снимок {j['result']['baseDate']}, монет {len(j['result']['elements'])}")
add("upbit_datalab_static_asset_status", "https://datalab-static.upbit.com/platform/v1/asset/status",
    lambda j: f"снимок, монет {len(j)}")
add("upbit_datalab_page", "https://datalab.upbit.com/assets/BTC/summary", None)
add("upbit_datalab_api", "https://datalab-api.upbit.com/", None)
# --- Корея: Bithumb
B = "https://gw.bithumb.com/exchange"
add("bithumb_wealthy_stat", B + "/v1/trade/indicator/wealthy/stat?coinType=C0565",
    lambda j: rng_list([{"t": int(datetime.fromisoformat(x["standardDate"]).replace(tzinfo=timezone.utc).timestamp() * 1000)}
                        for x in j["data"]["investList"]], "t"))
add("bithumb_wealthy_netbuy_rank", "https://gw.bithumb.com/public-info/v1/market-guide/wealthy/net-buying?count=10",
    lambda j: f"снимок {j['data']['timestamp']}")
add("bithumb_internal_supply", B + "/v1/trade/accumulation/deposit/C0565-C0100", lambda j: f"снимок {j['data']}")
add("bithumb_net_deposit_24h", B + "/v1/trade/purity/deposit/C0565-C0100", lambda j: f"снимок {j['data']}")
add("bithumb_holders", B + "/v1/trade/holders/C0565", lambda j: f"снимок {j['data']}")
add("bithumb_top10_holders", B + "/v1/trade/top/holder/share/C0565", lambda j: f"снимок {j['data']}")
add("bithumb_top10_traders", B + "/v1/trade/top/trader/share/C0565", lambda j: f"снимок {j['data']}")
add("bithumb_lending_assets", B + "/v1/lending/downturn/disclosure/assets-status",
    lambda j: f"снимок {j['data']['baseDateTime']}, монет {len(j['data']['items'])}")
add("bithumb_lending_autorepay", B + "/v1/lending/downturn/disclosure/auto-repayment/stats",
    lambda j: f"снимок {j['data']['baseDateTime']}, монет {len(j['data']['items'])}")
add("bithumb_surging_status", B + "/quote/v1/surging/capture/coins-status",
    lambda j: f"сегодняшние сигналы: {len(j['data']['captureCoinsStatus'])}")
add("bithumb_warning_history", B + "/v2/trade/virtual-asset/warning/history"
    "?startDate=2023-07-01&endDate=2023-07-10&crncCd=C0100&warningType=03&warningLevel=1&size=5",
    lambda j: f"с 03.07.2023 (s204); в ответе {len(j['data']['items'])} записей")
# --- Coinbase
add("coinbase_asset_stats", "https://api.coinbase.com/v2/assets/stats/5b71fc48-3dd3-540c-809b-f8c94d0e68b5",
    lambda j: "снимок; signals " + json.dumps(j["data"].get("signals"))[:200])
add("coinbase_price_page", "https://www.coinbase.com/price/bitcoin", None)
# --- Binance
add("binance_margin_debt_daily", "https://www.binance.com/bapi/margin/v1/public/margin/marketStats/marginDebt"
    "?asset=DOGE&period=24&limit=60", lambda j: rng_list(j["data"], "timestamp"))
add("binance_margin_debt_hourly", "https://www.binance.com/bapi/margin/v1/public/margin/marketStats/marginDebt"
    "?asset=DOGE&period=1&limit=48", lambda j: rng_list(j["data"], "timestamp"))
add("binance_web_lsr", "https://www.binance.com/bapi/futures/v1/public/future/data/global-long-short-account-ratio",
    lambda j: rng_list([{"t": t} for t in j["data"]["xAxis"]], "t"), "POST", {"name": "DOGEUSDT", "periodMinutes": 1440})
add("binance_square_hot", "https://www.binance.com/bapi/composite/v2/public/pgc/hashtag/hot-list",
    lambda j: f"снимок, хэштегов {len(j['data']['data'])}")
add("binance_web_page", "https://www.binance.com/en/futures/funding-history/perpetual/trading-data", None)
# --- OKX
O = "https://www.okx.com"
add("okx_loan_ratio_old", O + "/priapi/v5/rubik/stat/margin/loan-ratio?ccy=DOGE&period=1D"
    "&begin=2025-11-25T00:00:00Z&end=2026-01-01T00:00:00Z", lambda j: f"{j.get('msg') or len(j.get('data'))}")
add("okx_loan_ratio_180d", O + "/priapi/v5/rubik/stat/margin/loan-ratio?ccy=DOGE&period=1D"
    "&begin=2026-05-25T00:00:00Z&end=2026-07-01T00:00:00Z", lambda j: rng_list(j["data"], 0))
add("okx_top_trader_sentiment", O + "/priapi/v5/rubik/stat/contracts/top-trader-sentiment-index?ccy=BTC&period=1D",
    lambda j: rng_list(j["data"], 0))
add("okx_c2c_usdt_premium", O + "/v3/c2c/tickers/premiumRate/USDT?interval=2",
    lambda j: rng_list([{"t": t} for t in j["data"]["timestamps"]], "t"))
# --- Bybit, Bitget, HTX, Gate, MEXC
add("bybit_api", "https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=1d&limit=5", None)
add("bitget_capital_flows", "https://www.bitget.com/v1/kline/public/capitalFlows",
    lambda j: rng_list(j["data"], "ftime"), "POST", {"symbolId": "DOGEUSDT_SPBL", "limit": 96, "stepUnit": "15m"})
add("htx_elite_ratio", "https://api.hbdm.com/linear-swap-api/v1/swap_elite_account_ratio?contract_code=DOGE-USDT&period=1day",
    lambda j: rng_list(j["data"]["list"], "ts"))
add("gate_liq_orders_old", f"https://api.gateio.ws/api/v4/futures/usdt/liq_orders?contract=DOGE_USDT&from={NOW-86400*400}"
    f"&to={NOW-86400*400+3600}", lambda j: f"{len(j)} записей за час 400 сут назад")
add("gate_web", "https://www.gate.io/futures-data", None)
add("mexc_web", "https://www.mexc.com/futures/data", None)
# --- Hyperliquid
add("hl_hlp_positions", "https://d2v1fiwobg9w6.cloudfront.net/hlp_positions",
    lambda j: f"{len(j['chart_data'])} строк, {j['chart_data'][0]['time']} … {j['chart_data'][-1]['time']}")
add("hl_asxn_proxy", "https://api-hyperliquid.asxn.xyz/api/cloudfront/hlp_positions", None)
add("hl_leaderboard", "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard",
    lambda j: f"снимок, счетов {len(j['leaderboardRows'])}")


def main():
    print("s209 проба", datetime.now(timezone.utc).isoformat())
    for name, method, url, body, desc in P:
        c, h, b = fetch(url, method=method, body=body, timeout=120, gap=0.5)
        note = ""
        try:
            j = json.loads(b)
            with open(f"{EX}/{name}.json", "w") as f:
                if name.startswith("hl_hlp") or name == "hl_leaderboard":
                    json.dump({"note": "урезано до 50 строк", "head": (j.get("chart_data") or j.get("leaderboardRows"))[:50]},
                              f, ensure_ascii=False)
                else:
                    json.dump(j, f, ensure_ascii=False)
            note = desc(j) if desc and c == 200 else (json.dumps(j, ensure_ascii=False)[:150])
        except Exception as e:
            t = b[:2000].decode("utf-8", "replace")
            if "Cloudflare" in t or "cf-ray" in str(h).lower():
                note = "Cloudflare: " + ("заблокировано" if "blocked" in t else "проверка браузера")
            elif "Access Denied" in t:
                note = "Akamai: Access Denied"
            elif h.get("x-amzn-waf-action"):
                note = "AWS WAF: challenge"
            elif "CloudFront" in t:
                note = "CloudFront: доступ из страны закрыт"
            else:
                note = f"не JSON ({len(b)} байт): {t[:100]!r}"
        print(f"{name:34s} {c:4d}  {note}", flush=True)


if __name__ == "__main__":
    main()
