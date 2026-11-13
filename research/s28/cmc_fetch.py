"""s28 — разлоки токенов с CoinMarketCap без ключа (публичный data-api сайта):
  token-unlock/listing?start=<страница>&limit=100 — монеты с расписанием разлоков (s28/unlock_listing.json);
  token-unlock/event?cryptoId=<id>&type=past|upcoming&page=<n>&limit=100 — события разлока: время, объём, доля
  общего предложения, получатели (allocationName) и тип вестинга (cliff / linear); прошлые — от новых к старым,
  до 01.08.2024; кэш s28/ev/<id>_past.json и <id>_up.json;
  cryptocurrency/historical?id=<id>&convertId=2781&timeStart&timeEnd — дневные цена, оборот, капитализация и монеты в
  обращении; кэш s28/hist/<id>.json.
Только монеты с фьючерсом Binance (s2/k2y.pkl) по тикеру. Пауза ~1 с между запросами. Запуск из папки с данными:
python3 cmc_fetch.py events | hist"""
import json
import os
import pickle
import sys
import time
import urllib.error
import urllib.request

API = "https://api.coinmarketcap.com/data-api/v3"
SINCE = "2024-08-01"


def get(url):
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)", "Accept": "application/json"})
            out = json.loads(urllib.request.urlopen(req, timeout=60).read())
            time.sleep(1.0)
            return out
        except urllib.error.HTTPError as e:
            time.sleep(60 if e.code == 429 else 5 + 5 * i)
        except Exception:
            time.sleep(5 + 5 * i)
    return None


def tokens():
    K = pickle.load(open("s2/k2y.pkl", "rb")); syms = set(K)
    out = []
    for r in json.load(open("s28/unlock_listing.json")):
        for p in ("", "1000", "1000000"):
            if p + r["symbol"] in syms:
                out.append((r["cryptoId"], r["symbol"], p + r["symbol"])); break
    return out


def events(cid):
    path = f"s28/ev/{cid}_past.json"
    if not os.path.exists(path):
        ev, page = [], 1
        while True:
            d = get(f"{API}/token-unlock/event?cryptoId={cid}&type=past&page={page}&limit=100")
            if d is None or "data" not in d:
                break
            x = d["data"].get("tokenEvent") or []
            ev += x
            if len(x) < 100 or x[-1]["time"][:10] < SINCE:
                break
            page += 1
        json.dump(ev, open(path, "w"))
    path = f"s28/ev/{cid}_up.json"
    if not os.path.exists(path):
        d = get(f"{API}/token-unlock/event?cryptoId={cid}&type=upcoming&page=1&limit=100")
        json.dump((d or {}).get("data", {}).get("tokenEvent") or [], open(path, "w"))


def hist(cid):
    path = f"s28/hist/{cid}.json"
    if os.path.exists(path):
        return
    out = []
    for t0, t1 in ((1722470400, 1754006400), (1754006400, 1794614400)):      # 01.08.2024–01.08.2025–13.11.2026
        d = get(f"{API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={t0}&timeEnd={t1}&interval=1d")
        if d is None or "data" not in d:
            return
        for q in d["data"].get("quotes") or []:
            u = q["quote"]
            out.append([q["timeClose"][:10], u.get("close"), u.get("volume"), u.get("marketCap"), u.get("circulatingSupply")])
    json.dump(out, open(path, "w"))


if __name__ == "__main__":
    mode = sys.argv[1]
    os.makedirs("s28/ev", exist_ok=True); os.makedirs("s28/hist", exist_ok=True)
    T = tokens()
    print(f"монет с фьючерсом Binance: {len(T)}", flush=True)
    for n, (cid, sym, fut) in enumerate(T):
        (events if mode == "events" else hist)(cid)
        if n % 50 == 0:
            print(f"  {mode} {n}/{len(T)}", flush=True)
    print("готово", flush=True)
