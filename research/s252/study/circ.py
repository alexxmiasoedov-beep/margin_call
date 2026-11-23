"""s252 — для токенов BNB Chain у перпов без спота Binance: десятичные знаки и выпуск в BNB Chain (eth_call к публичному
узлу), монета CoinMarketCap и её история монет в обращении (data-api без ключа).
Монета CMC: та, у которой адрес платформы равен адресу в BNB Chain (map/all — s167/cmc_map_all.json), иначе с тем же
тикером и медианой цены к перпу 0,8–1,25 (свечи s2/k2y.pkl), как в s249/circ.py. История — `cryptocurrency/historical`
с 01.10.2024; чужие кэши (s171/cmc, s249/cmc_early) только читаются, свой — s252/cmc/<id>.json.
Итог — /home/user/mc_data/s252/bsc_tokens.json: {перп: {contract, decimals, bsc_supply, cmc, cmc_name, match, days: [[дата,
в обращении, цена], …]}}. Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/circ.py"""
import json
import os
import pickle
import re
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

API = "https://api.coinmarketcap.com/data-api/v3"
UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}
RPC = ["https://bsc-rpc.publicnode.com", "https://bsc-dataseed.bnbchain.org", "https://bsc-dataseed.binance.org"]
EDGES = ["2024-10-01", "2025-06-30", "2026-01-31", "2026-11-22"]


def get(url):
    for i in range(6):
        try:
            out = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(0.5)
            return out
        except urllib.error.HTTPError as e:
            time.sleep(60 if e.code == 429 else 4 + 4 * i)
        except Exception:  # noqa: BLE001
            time.sleep(4 + 4 * i)
    return None


def call(to, data):
    for i in range(6):
        u = RPC[i % len(RPC)]
        try:
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": to, "data": data}, "latest"]})
            r = json.loads(urllib.request.urlopen(urllib.request.Request(u, data=body.encode(), headers={
                "Content-Type": "application/json", "User-Agent": "research-script/1.0"}), timeout=30).read())
            if "result" in r:
                return r["result"]
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1 + i)
    return None


def base(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    if m and not m.group(2)[0].isdigit():
        return m.group(2), 1e6 if m.group(1) in ("1M", "1000000") else float(m.group(1))
    return fs, 1.0


def hist(cid):
    path = f"s252/cmc/{cid}.json"
    if os.path.exists(path):
        return json.load(open(path))
    by = {}
    for p in (f"s249/cmc_early/{cid}.json", f"s171/cmc/{cid}.json"):      # чужие кэши — только чтение
        if os.path.exists(p):
            for r in json.load(open(p)):
                by[r[0]] = r
    have = sorted(by)
    for a, b in zip(EDGES[:-1], EDGES[1:]):
        if have and sum(1 for d in have if a <= d < b) >= 0.9 * (pd.Timestamp(b) - pd.Timestamp(a)).days:
            continue
        t0, t1 = (int(pd.Timestamp(x, tz="UTC").timestamp()) for x in (a, b))
        d = get(f"{API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={t0}&timeEnd={t1}&interval=1d")
        for q in ((d or {}).get("data") or {}).get("quotes") or []:
            u = q["quote"]
            by[q["timeClose"][:10]] = [q["timeClose"][:10], u.get("circulatingSupply"), u.get("close"), u.get("marketCap")]
    out = [by[d] for d in sorted(by)]
    os.makedirs("s252/cmc", exist_ok=True)
    json.dump(out, open(path, "w"))
    return out


def main():
    TK = json.load(open("s252/tokens.json"))
    cmc = json.load(open("s167/cmc_map_all.json"))
    by_sym, by_addr = {}, {}
    for c in cmc:
        by_sym.setdefault(str(c.get("symbol") or "").upper(), []).append(c)
        p = c.get("platform")
        if isinstance(p, dict) and p.get("token_address"):
            by_addr.setdefault(str(p["token_address"]).lower(), []).append(c)
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    out = json.load(open("s252/bsc_tokens.json")) if os.path.exists("s252/bsc_tokens.json") else {}
    for s, r in sorted(TK.items()):
        if not r.get("bsc") or s in out:
            continue
        a = r["bsc"]
        dec = call(a, "0x313ce567")
        sup = call(a, "0x18160ddd")
        dec = int(dec, 16) if dec and dec != "0x" else None
        sup = int(sup, 16) / 10 ** dec if (sup and sup != "0x" and dec is not None) else None
        fs = s[:-4]
        coin, mult = base(fs)
        best, how = None, None
        same = [c for c in by_addr.get(a, []) if str(c.get("symbol") or "").upper() in (coin.upper(), r["base"].upper())]
        if same:
            same.sort(key=lambda c: -int(c.get("is_active") or 0))
            best, how = same[0], "адрес"
        elif fs in K:
            k = K[fs]
            m = (k["qv"] > 0) & (k["t"] % 86400 == 86400 - 900)
            px = pd.Series(k["c"][m].astype(float) / mult,
                           index=pd.to_datetime(k["t"][m].astype(np.int64) // 86400 * 86400, unit="s").strftime("%Y-%m-%d"))
            rr_best = None
            for c in by_sym.get(coin.upper(), []):
                if not c.get("is_active") and c.get("last_historical_data", "")[:4] < "2025":
                    continue
                h = hist(c["id"])
                q = pd.Series({d: cl for d, _, cl, _ in h if cl}, dtype=float)
                j = q.index.intersection(px.index)
                if len(j) < 20:
                    continue
                rr = float(np.median(q[j].values / px[j].values))
                if 0.8 <= rr <= 1.25 and (rr_best is None or abs(np.log(rr)) < abs(np.log(rr_best))):
                    best, how, rr_best = c, f"тикер, цена {rr:.2f}", rr
        rec = {"contract": a, "decimals": dec, "bsc_supply": sup, "cmc": None, "match": how}
        if best:
            h = hist(best["id"])
            rec.update(cmc=best["id"], cmc_name=best.get("name"),
                       days=[[d, ci, cl] for d, ci, cl, _ in h if ci and cl])
        out[s] = rec
        last = rec.get("days", [[None, None, None]])[-1]
        print(s, dec, f"{sup:.4g}" if sup else sup, best["id"] if best else "—", how, "дней", len(rec.get("days", [])),
              "в обращении (последнее)", last[1], flush=True)
        json.dump(out, open("s252/bsc_tokens.json", "w"))
    print("готово:", len(out), "с CMC:", sum(1 for v in out.values() if v.get("cmc")))


if __name__ == "__main__":
    main()
