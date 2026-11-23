"""s252 — класс (в), проверка по сделкам за последние 24 ч (GeckoTerminal `pools/<пул>/trades`, публичный API отдаёт только
последние сутки, до 300 сделок, фильтр `trade_volume_in_usd_greater_than`). Для главного пула каждого токена группы H —
продажи токена (kind = sell) не меньше 0,1% капитализации в обращении (CMC, последний день). Даёт число крупных
одиночных продаж на токен в сутки и отношение «крупнейшая продажа часа / оборот часа» для калибровки dex_cand.py.
Итог — /home/user/mc_data/s252/dex_trades24.json. Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/dex_trades24.py"""
import json
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}
URL = "https://api.geckoterminal.com/api/v2/networks/bsc/pools/{}/trades?trade_volume_in_usd_greater_than={:.0f}"


def get(url):
    for i in range(6):
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(6.5)
            return d
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 404):
                time.sleep(3)
                return {"err": e.code}
            time.sleep(65 if e.code == 429 else 5 + 5 * i)
        except Exception:  # noqa: BLE001
            time.sleep(5 + 5 * i)
    return None


def main():
    TK = json.load(open("s252/tokens.json"))
    TB = json.load(open("s252/bsc_tokens.json"))
    DP = json.load(open("s252/dex_pairs.json"))
    out = {}
    for s in sorted(DP):
        v = TB.get(s) or {}
        if TK[s].get("alpha_chain") != "bsc" or not TK[s]["bsc_native"] or not v.get("days"):
            continue
        if not v.get("bsc_supply") or v["bsc_supply"] < 0.5 * v["days"][-1][1]:
            continue
        pools = [p for p in DP[s] if (p["liq"] or 0) >= 20000][:1]
        if not pools:
            continue
        p = pools[0]
        d0, ci, px = v["days"][-1]
        mcap = ci * px
        d = get(URL.format(p["pair"], 0.001 * mcap))
        tr = []
        for x in (d or {}).get("data") or []:
            a = x.get("attributes") or {}
            tok_in = str(a.get("from_token_address") or "").lower()
            tr.append({"t": a.get("block_timestamp"), "kind": a.get("kind"), "usd": float(a.get("volume_in_usd") or 0),
                       "sell_token": tok_in == v["contract"], "tx": a.get("tx_hash"), "from": a.get("tx_from_address")})
        out[s] = {"pool": p["pair"], "mcap": mcap, "day": d0, "trades": tr, "err": (d or {}).get("err")}
        big = [x for x in tr if x["sell_token"]]
        print(s, f"капитализация {mcap / 1e6:.1f} млн $, сделок ≥ 0,1% за сутки {len(tr)}, продаж токена {len(big)}, "
              f"≥ 0,25%: {sum(1 for x in big if x['usd'] >= 0.0025 * mcap)}", flush=True)
    json.dump(out, open("s252/dex_trades24.json", "w"), indent=0)


if __name__ == "__main__":
    main()
