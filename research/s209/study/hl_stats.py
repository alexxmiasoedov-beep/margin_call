#!/usr/bin/env python3
"""s209: история статистики Hyperliquid по монетам (официальный CloudFront страницы статистики).

Ключ: stats.hyperliquid.xyz → hyperscreener.asxn.xyz (бандл index-*.js) → пути `/cloudfront/<имя>`.
Прокси ASXN (api-hyperliquid.asxn.xyz) требует пройти проверку («VERIFICATION_REQUIRED») — не обходим;
те же файлы отдаёт официальный CloudFront Hyperliquid https://d2v1fiwobg9w6.cloudfront.net/<имя> без ключа.

Пишет /home/user/mc_data/s209/hl/<имя>.json.gz и сводку в stdout: число строк, монет, даты, сколько монет
совпадает с перпами Binance (ключи s2/k2y).
"""
import gzip, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common209 import fetch, perp_bases

OUT = "/home/user/mc_data/s209/hl"
BASE = "https://d2v1fiwobg9w6.cloudfront.net/"
NAMES = [
    "hlp_positions", "daily_notional_liquidated_by_coin", "v2/daily_notional_liquidated_by_coin",
    "daily_unique_users_by_coin", "open_interest", "funding_rate", "daily_usd_volume_by_coin",
    "daily_trades_by_coin", "v2/daily_trades_by_coin", "liquidity_by_coin", "daily_notional_liquidated_by_leverage_type",
    "hlp_liquidator_pnl", "cumulative_hlp_liquidator_pnl", "daily_inflow", "daily_unique_users", "daily_usd_volume",
    "largest_users_by_usd_volume", "largest_user_depositors", "largest_liquidated_notional_by_user",
    "largest_user_trade_count", "asset_ctxs", "slippage_by_coin", "total_open_interest", "daily_usd_volume_by_crossed",
]


def main():
    os.makedirs(OUT, exist_ok=True)
    perps = perp_bases()
    for name in NAMES:
        t0 = time.time()
        c, h, b = fetch(BASE + name, timeout=180, gap=1.0)
        fn = os.path.join(OUT, name.replace("/", "_") + ".json.gz")
        if c != 200:
            print(f"{name}: HTTP {c} {b[:120]!r}", flush=True)
            continue
        with gzip.open(fn, "wb") as f:
            f.write(b)
        try:
            j = json.loads(b)
        except Exception as e:
            print(f"{name}: не JSON ({e})", flush=True)
            continue
        rows = j.get("chart_data") if isinstance(j, dict) else j
        if not isinstance(rows, list) or not rows:
            ks = list(j.keys())[:10] if isinstance(j, dict) else type(j).__name__
            print(f"{name}: {len(b)/1e6:.1f} МБ, ключи {ks}", flush=True)
            continue
        cols = sorted(rows[0].keys())
        times = [r.get("time") for r in rows if r.get("time")]
        coins = {r.get("coin") for r in rows if r.get("coin")}
        hit = {c for c in coins if c and (c in perps or c.lstrip("k") in perps)}
        print(f"{name}: {len(b)/1e6:.1f} МБ за {time.time()-t0:.0f} с, строк {len(rows)}, поля {cols}, "
              f"даты {min(times) if times else '-'} … {max(times) if times else '-'}, монет {len(coins)}, "
              f"из них с перпом Binance {len(hit)}", flush=True)


if __name__ == "__main__":
    main()
