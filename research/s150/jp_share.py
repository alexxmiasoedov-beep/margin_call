# Доля японских (и др. изолированных) бирж в обороте монет с перпом Binance — снимок 24 ч
import json, urllib.request, time, sys
UA = {"User-Agent": "research-script/1.0"}
def get(u, tries=2):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            err = e; time.sleep(1)
    print("FAIL", u, err, file=sys.stderr); return None
fx = get("https://api.frankfurter.app/latest?from=USD&to=JPY,PHP")
usdjpy = fx["rates"]["JPY"]; usdphp = fx["rates"]["PHP"]
print("USDJPY", usdjpy, "USDPHP", usdphp)
perp = get("https://www.binance.com/fapi/v1/ticker/24hr")
pv = {}
for x in perp:
    s = x["symbol"]
    if s.endswith("USDT"):
        b = s[:-4]
        for p in ("1000000", "1000", "1M"):
            if b.startswith(p) and len(b) > len(p): b = b[len(p):]
        pv[b] = pv.get(b, 0) + float(x["quoteVolume"])
spot = get("https://data-api.binance.vision/api/v3/ticker/24hr?type=MINI")
sv = {}
for x in spot:
    s = x["symbol"]
    for q in ("USDT", "USDC", "FDUSD"):
        if s.endswith(q):
            b = s[:-len(q)]; sv[b] = sv.get(b, 0) + float(x["quoteVolume"])
jp = {}
def add(src, b, usd):
    b = b.upper()
    jp.setdefault(b, {}); jp[b][src] = jp[b].get(src, 0) + usd
bb = get("https://public.bitbank.cc/tickers")
for x in bb["data"]:
    if x["pair"].endswith("_jpy") and x["last"]:
        add("bitbank", x["pair"][:-4], float(x["vol"]) * float(x["last"]) / usdjpy)
gm = get("https://api.coin.z.com/public/v1/ticker")
for x in gm["data"]:
    s = x["symbol"]
    if "_" in s: continue  # leverage pairs like BTC_JPY
    add("gmo", s, float(x["volume"]) * float(x["last"]) / usdjpy)
bt = get("https://api-cloud.bittrade.co.jp/market/tickers")
if bt:
    for x in bt.get("data", []):
        s = x["symbol"]
        if s.endswith("jpy"):
            add("bittrade", s[:-3], float(x.get("vol") or 0) / usdjpy)
for pc in ["BTC_JPY","XRP_JPY","ETH_JPY","XLM_JPY","MONA_JPY","ELF_JPY"]:
    t = get("https://api.bitflyer.com/v1/ticker?product_code=" + pc)
    if t: add("bitflyer", pc.split("_")[0], float(t["volume_by_product"]) * float(t["ltp"]) / usdjpy)
cc_pairs = ["btc","eth","etc","lsk","xrp","xem","bch","mona","iost","enj","chz","imx","shib","avax","fnct","dai","wbtc","bril","bc","sand","doge","pepe","mask","mana","trx","grt","pol","sol","ape","axs","dot","link","ltc","bat","xlm","qtum","fct","plt","op","arb","sui","nidt","dep"]
for c in cc_pairs:
    t = get(f"https://coincheck.com/api/ticker?pair={c}_jpy", tries=1)
    if t and "last" in t and t["last"]:
        add("coincheck", c, float(t["volume"]) * float(t["last"]) / usdjpy)
    time.sleep(0.15)
ph = {}
cp = get("https://api.pro.coins.ph/openapi/quote/v1/ticker/24hr")
for x in cp or []:
    s = x["symbol"]
    if s.endswith("PHP"):
        ph[s[:-3]] = ph.get(s[:-3], 0) + float(x["quoteVolume"]) / usdphp
us = {}
bu = get("https://api.binance.us/api/v3/ticker/24hr")
for x in bu or []:
    s = x["symbol"]
    for q in ("USDT", "USDC", "USD"):
        if s.endswith(q) and not s.endswith("USD4"):
            us[s[:-len(q)]] = us.get(s[:-len(q)], 0) + float(x["quoteVolume"]); break
rows = []
for b in sorted(set(jp) | set(ph) | set(us)):
    if b not in pv: continue
    glob = pv.get(b, 0) + sv.get(b, 0)
    j = sum(jp.get(b, {}).values())
    rows.append((b, glob, j, ph.get(b, 0), us.get(b, 0)))
tot_j = sum(r[2] for r in rows); tot_g = sum(r[1] for r in rows)
print(f"монет с перпом Binance и рынком JP/PH/US: {len(rows)}; JP всего ${tot_j/1e6:.1f}M; PH ${sum(r[3] for r in rows)/1e6:.1f}M; Binance.US ${sum(r[4] for r in rows)/1e6:.1f}M; Binance perp+spot этих монет ${tot_g/1e9:.1f}B")
print("JP монет с перпом:", sum(1 for r in rows if r[2] > 0))
print("Топ доли Японии (JP / Binance perp+spot):")
for r in sorted(rows, key=lambda r: -r[2] / max(r[1], 1))[:30]:
    print(f"  {r[0]:8s} Binance ${r[1]/1e6:9.1f}M  JP ${r[2]/1e6:7.2f}M  {100*r[2]/max(r[1],1):6.2f}%   {jp.get(r[0],{})}")
print("Топ доли Coins.ph:")
for r in sorted(rows, key=lambda r: -r[3] / max(r[1], 1))[:8]:
    print(f"  {r[0]:8s} Binance ${r[1]/1e6:9.1f}M  PH ${r[3]/1e6:7.3f}M  {100*r[3]/max(r[1],1):6.3f}%")
print("Топ доли Binance.US:")
for r in sorted(rows, key=lambda r: -r[4] / max(r[1], 1))[:8]:
    print(f"  {r[0]:8s} Binance ${r[1]/1e6:9.1f}M  US ${r[4]/1e6:7.3f}M  {100*r[4]/max(r[1],1):6.3f}%")
json.dump({"jp": jp, "ph": ph, "us": us, "pv": pv, "sv": sv}, open(sys.argv[1], "w"))
