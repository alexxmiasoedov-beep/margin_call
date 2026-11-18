import sys, time, collections
sys.path.insert(0, sys.argv[1])
from edgar_fts import all_hits
coins = [("SOL", '"SOL" "treasury" "acquired"'), ("HYPE", '"HYPE" "treasury"'), ("SUI", '"SUI" "treasury"'), ("TON", '"Toncoin"'),
         ("AVAX", '"AVAX" "treasury"'), ("LTC", '"Litecoin" "treasury"'), ("ENA", '"ENA" "treasury"'), ("WLD", '"WLD" "treasury"'),
         ("IP", '"IP tokens"'), ("INJ", '"INJ" "treasury"'), ("TAO", '"TAO" "treasury"'), ("ZEC", '"ZEC" "treasury"'),
         ("DOGE", '"Dogecoin" "treasury"'), ("XRP", '"XRP" "treasury"'), ("TRX", '"TRX" "treasury"'), ("BNB", '"BNB" "treasury"'),
         ("LINK", '"LINK" "treasury"'), ("NEAR", '"NEAR" "treasury"'), ("SEI", '"SEI" "treasury"'), ("0G", '"0G" "treasury"'),
         ("CRO", '"CRO" "treasury"'), ("WLFI", '"WLFI" "treasury"'), ("BONK", '"BONK" "treasury"'), ("FET", '"FET" "treasury"')]
print("монета | 8-K за 2025-07..2025-12 | 8-K за 2026-01..2026-11 | компаний (2026)")
for c, q in coins:
    try:
        h1, t1 = all_hits(q, "8-K", "2025-07-01", "2025-12-31", maxn=1)
        h2, t2 = all_hits(q, "8-K", "2026-01-01", "2026-11-18", maxn=400)
        names = collections.Counter((h["_source"].get("display_names") or ["?"])[0][:40] for h in h2)
        print(f"{c:5s} | {t1:4d} | {t2:4d} | {len(names):3d} | {'; '.join(n for n, _ in names.most_common(4))}")
    except Exception as e:
        print(c, "ERR", e)
    time.sleep(0.5)
