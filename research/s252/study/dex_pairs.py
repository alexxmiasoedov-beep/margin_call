"""s252 — пулы DEX в BNB Chain для токенов перпов без спота (DexScreener `token-pairs/v1/bsc/<адрес>`, без ключа, снимок
«сейчас»: адрес пула, DEX и версия, пара, ликвидность, сделки за 24 ч, дата создания).
Итог — /home/user/mc_data/s252/dex_pairs.json: {перп: [пул, …]}. Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/dex_pairs.py"""
import json
import time
import urllib.request

TK = json.load(open("s252/tokens.json"))
out = {}
for s, r in sorted(TK.items()):
    if not r.get("bsc"):
        continue
    url = f"https://api.dexscreener.com/token-pairs/v1/bsc/{r['bsc']}"
    d = None
    for i in range(4):
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-script/1.0"}),
                                                  timeout=30).read())
            break
        except Exception:  # noqa: BLE001
            time.sleep(3 + 3 * i)
    rows = []
    for p in d or []:
        rows.append({"dex": p.get("dexId"), "ver": (p.get("labels") or [None])[0], "pair": str(p.get("pairAddress")),
                     "base": p["baseToken"]["address"].lower(), "quote": p["quoteToken"]["address"].lower(),
                     "qsym": p["quoteToken"]["symbol"], "liq": (p.get("liquidity") or {}).get("usd"),
                     "tx24": sum(((p.get("txns") or {}).get("h24") or {}).values()), "vol24": (p.get("volume") or {}).get("h24"),
                     "created": p.get("pairCreatedAt")})
    rows.sort(key=lambda x: -(x["liq"] or 0))
    out[s] = rows
    top = rows[0] if rows else {}
    print(s, len(rows), top.get("dex"), top.get("ver"), top.get("qsym"), top.get("liq"), top.get("tx24"), flush=True)
    time.sleep(0.4)
json.dump(out, open("s252/dex_pairs.json", "w"), indent=0)
