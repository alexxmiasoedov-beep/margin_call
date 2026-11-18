"""s160 — монеты в обращении по дням для токенов s160/sets.json из CMC data-api без ключа: список CMC (тикер, id, капитализация)
→ id по тикеру и ближайшей капитализации к CoinGecko; история `cryptocurrency/historical` по годам с 01.09.2020.
Итог — s160/circ/<id>.json ([[дата, обращение, цена]]) и s160/cmc_ids.json. Запуск из /home/user/mc_data."""
import json
import os
import time
import urllib.error
import urllib.request

API = "https://api.coinmarketcap.com/data-api/v3"
UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}


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


def ids():
    path = "s160/cmc_ids.json"
    if os.path.exists(path):
        return json.load(open(path))
    L = []
    for start in (1, 5001):
        d = get(f"{API}/cryptocurrency/listing?start={start}&limit=5000&sortBy=market_cap&sortType=desc&convert=USD&cryptoType=all&tagType=all&audited=false")
        L += (d or {}).get("data", {}).get("cryptoCurrencyList") or []
    by = {}
    for x in L:
        mc = next((q.get("marketCap") for q in x.get("quotes") or [] if q.get("name") == "USD"), None)
        by.setdefault(x["symbol"].upper(), []).append((x["id"], x["slug"], mc or 0))
    S = json.load(open("s160/sets.json"))["toks"]
    out = {}
    for tok, v in S.items():
        cands = by.get(str(v["sym"]).upper()) or []
        if not cands:
            continue
        m0 = float(v.get("mcap") or 0)
        best = min(cands, key=lambda c: abs((c[2] or 0) - m0) / max(m0, 1))
        out[tok] = {"id": best[0], "slug": best[1], "sym": v["sym"], "perp": v["perp"]}
    json.dump(out, open(path, "w"))
    return out


def hist(cid):
    path = f"s160/circ/{cid}.json"
    if os.path.exists(path):
        return
    out = []
    edges = [1598918400 + k * 31_536_000 for k in range(8)]          # 01.09.2020 + годы
    for t0, t1 in zip(edges[:-1], edges[1:]):
        d = get(f"{API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={t0}&timeEnd={min(t1, 1795000000)}&interval=1d")
        for q in ((d or {}).get("data") or {}).get("quotes") or []:
            u = q["quote"]
            out.append([q["timeClose"][:10], u.get("circulatingSupply"), u.get("close")])
        if t1 > 1795000000:
            break
    json.dump(out, open(path, "w"))


def main():
    os.makedirs("s160/circ", exist_ok=True)
    M = ids()
    print("сопоставлено токенов", len(M), flush=True)
    for k, v in enumerate(M.values()):
        hist(v["id"])
        if k % 25 == 0:
            print(k, flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
