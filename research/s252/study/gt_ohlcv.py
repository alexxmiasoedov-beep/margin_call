"""s252 — часовой оборот пулов DEX (GeckoTerminal, публичный API без ключа: только последние 180 сут; на деле ~10 запросов в минуту)
для токенов BNB Chain перпов без спота, группа H (выпуск в BNB Chain ≥ 50% монет в обращении). Пул — главный по
ликвидности (DexScreener, s252/dex_pairs.json), ≥ 20 тыс. $; для первых 6 токенов по алфавиту собраны и вторые пулы. Нужен как необходимое условие для класса (в) «крупная продажа на DEX»: продажа на X $ в часе
даёт оборот часа ≥ X $, значит, разбирать сделки надо только в часах с оборотом ≥ порога.
Итог — /home/user/mc_data/s252/gt/<пул>.json: [[время, o, h, l, c, оборот $], …].
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/gt_ohlcv.py"""
import json
import os
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}
URL = ("https://api.geckoterminal.com/api/v2/networks/bsc/pools/{}/ohlcv/hour?aggregate=1&limit=1000"
       "&before_timestamp={}&currency=usd")


def get(url):
    for i in range(6):
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(6.5)
            return d
        except urllib.error.HTTPError as e:
            if e.code == 401 or e.code == 404:
                time.sleep(2.2)
                return {"err": e.code}
            time.sleep(65 if e.code == 429 else 5 + 5 * i)
        except Exception:  # noqa: BLE001
            time.sleep(5 + 5 * i)
    return None


def main():
    TK = json.load(open("s252/tokens.json"))
    TB = json.load(open("s252/bsc_tokens.json"))
    DP = json.load(open("s252/dex_pairs.json"))
    os.makedirs("s252/gt", exist_ok=True)
    now = int(time.time())
    lo = now - 179 * 86400
    for s in sorted(DP):
        if TK[s].get("alpha_chain") != "bsc" or not TK[s]["bsc_native"]:
            continue
        v = TB.get(s) or {}
        if not v.get("days") or not v.get("bsc_supply") or v["bsc_supply"] < 0.5 * v["days"][-1][1]:
            continue                                   # только группа H: выпуск в BNB Chain ≥ 50% монет в обращении
        pools = [p for p in DP[s] if (p["liq"] or 0) >= 20000][:1]   # главный пул (ликвидность ≥ 20 тыс. $)
        for p in pools:
            f = f"s252/gt/{p['pair'].lower()}.json"
            if os.path.exists(f):
                continue
            rows, before = {}, now
            while before > lo:
                d = get(URL.format(p["pair"], before))
                L = (((d or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
                if not L:
                    break
                for r in L:
                    rows[int(r[0])] = r
                mn = min(int(r[0]) for r in L)
                if mn >= before:
                    break
                before = mn
            out = [rows[t] for t in sorted(rows) if t >= lo]
            json.dump(out, open(f, "w"))
            print(s, p["dex"], p["ver"], p["pair"][:12], "часов", len(out), flush=True)


if __name__ == "__main__":
    main()
