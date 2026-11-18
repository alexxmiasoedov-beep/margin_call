"""s167 — токены проверки: фьючерсы USDT-M периодов 10.2020–09.2022 и 10.2022–09.2024, которых нет в карте s160, с контрактом ERC-20.
Кандидаты — монеты CMC (data-api map/all, все статусы) с тем же тикером; монета CMC выбирается по цене: медиана отношения цены
закрытия CMC к цене фьючерса (с учётом множителя 1000…) за дни торгов 0,8–1,25, не меньше 20 дней, ближе к 1. Контракт ERC-20 —
платформа CMC (если Ethereum), иначе монета CoinGecko с тем же id/slug или названием, иначе единственная монета CoinGecko с тем же
тикером и платформой Ethereum. Контракты из набора s160 исключаются. Итог — s167/toks.json и s167/circ/<id>.json
([[дата, обращение, цена]]). Запуск из /home/user/mc_data: python3 <repo>/research/s167/tokens.py"""
import json
import os
import pickle
import re
import sys
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

API = "https://api.coinmarketcap.com/data-api/v3"
UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}
CG = "/tmp/claude-0/-home-user/73eaf1da-1cd7-57de-90aa-695a4f698551/scratchpad/study3/cg_plat.json"
SKIP = {"BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD", "BTT"}            # индексы; BTT — старый TRC-10, ERC-20 есть только у нового


def get(url):
    for i in range(6):
        try:
            out = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(0.5)
            return out
        except urllib.error.HTTPError as e:
            time.sleep(60 if e.code == 429 else 5 + 5 * i)
        except Exception:
            time.sleep(5 + 5 * i)
    return None


def hist(cid):
    path = f"s167/circ/{cid}.json"
    if os.path.exists(path):
        return json.load(open(path))
    out = []
    edges = [1598918400 + k * 31_536_000 for k in range(5)]          # 01.09.2020 + годы, до 09.2024
    for t0, t1 in zip(edges[:-1], edges[1:]):
        d = get(f"{API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={t0}&timeEnd={t1}&interval=1d")
        for q in ((d or {}).get("data") or {}).get("quotes") or []:
            u = q["quote"]
            out.append([q["timeClose"][:10], u.get("circulatingSupply"), u.get("close")])
    json.dump(out, open(path, "w"))
    return out


def base(p):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", p)
    return (m.group(2), 1_000_000 if m.group(1) in ("1M", "1000000") else int(m.group(1))) if m else (p, 1)


def daily_close(K, s):
    a = K[s]; t = a["t"].astype(np.int64); c = a["c"].astype(float); v = a["qv"].astype(float)
    m = (t % 86400 == 86400 - 900) & (v > 0)                            # последняя 15-мин свеча суток с оборотом
    return pd.Series(c[m], index=pd.to_datetime(t[m] // 86400 * 86400, unit="s").strftime("%Y-%m-%d"))


def main():
    os.makedirs("s167/circ", exist_ok=True)
    have = {r["perp"] for r in json.load(open("s160/perp_map.json"))}
    s160 = set(json.load(open("s160/sets.json"))["toks"])
    cmc = json.load(open("s167/cmc_map_all.json")); cg = json.load(open(CG))
    by_sym = {}
    for c in cmc:
        by_sym.setdefault(str(c.get("symbol", "")).upper(), []).append(c)
    cg_by_id = {c["id"]: c for c in cg}
    cg_by_name, cg_by_sym = {}, {}
    for c in cg:
        eth = (c.get("platforms") or {}).get("ethereum")
        if eth:
            cg_by_name.setdefault(c["name"].lower(), []).append(eth.lower())
            cg_by_sym.setdefault(c["symbol"].upper(), []).append(eth.lower())
    out, log = {}, []
    for f in ("s117/k_2020.pkl", "s117/k_oos.pkl"):
        K = pickle.load(open(f, "rb"))
        for p in sorted(K):
            if p in have or p in SKIP or any(v["perp"] == p for v in out.values()):
                continue
            b, mult = base(p)
            cands = by_sym.get(b.upper(), [])
            if not cands:
                log.append((p, "нет монеты CMC с тикером")); continue
            px = daily_close(K, p) / mult
            best = None
            for c in cands:
                h = hist(c["id"])
                if not h:
                    continue
                q = pd.Series({d: cl for d, _, cl in h if cl}, dtype=float)
                j = q.index.intersection(px.index)
                if len(j) < 20:
                    continue
                r = float(np.median(q[j].values / px[j].values))
                if 0.8 <= r <= 1.25 and (best is None or abs(np.log(r)) < abs(np.log(best[1]))):
                    best = (c, r, len(j))
            if best is None:
                log.append((p, "цена CMC не сходится ни у одного кандидата")); continue
            c = best[0]; pl = c.get("platform") or {}
            eth = pl.get("token_address", "").lower() if pl.get("slug") == "ethereum" else None
            if not eth:
                g = cg_by_id.get(c["slug"])
                eth = ((g or {}).get("platforms") or {}).get("ethereum")
                eth = eth.lower() if eth else None
            if not eth and len(cg_by_name.get(c["name"].lower(), [])) == 1:
                eth = cg_by_name[c["name"].lower()][0]
            if not eth and len(cg_by_sym.get(b.upper(), [])) == 1:
                eth = cg_by_sym[b.upper()][0]
            if not eth or not eth.startswith("0x") or len(eth) != 42:
                log.append((p, f"нет контракта ERC-20 (CMC {c['id']} {c['name']})")); continue
            if eth in s160:
                log.append((p, "контракт уже в наборе s160")); continue
            circ = [x for x in hist(c["id"]) if x[1]]
            if not circ:
                log.append((p, f"нет обращения CMC ({c['id']})")); continue
            out[eth] = {"perp": p, "sym": b, "mult": mult, "cmc": c["id"], "name": c["name"], "ratio": round(best[1], 3),
                        "days": best[2]}
            print(p, c["id"], c["name"], eth, round(best[1], 3), flush=True)
        del K
    json.dump(out, open("s167/toks.json", "w"))
    for p, why in log:
        print("  исключён", p, "—", why)
    print("токенов", len(out))


if __name__ == "__main__":
    main()
