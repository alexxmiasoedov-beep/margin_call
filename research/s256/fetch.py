"""s256 — часовые свечи Binance Alpha для монет фьючерсов, которые были без спота Binance (s253: spot_dates + spot1h).
Список Alpha — снимок s252/alpha_tokens.json (alphaId, symbol, listingTime). Сопоставление монеты фьючерса с токеном Alpha:
тот же тикер (без учёта регистра, с учётом приставок 1000/1M), цена Alpha к цене фьючерса 0,8–1,25 в последний общий час
(свечи фьючерса s2/k2y.pkl); если подходят несколько — наибольшая капитализация. Свечи —
www.binance.com/bapi/defi/v1/public/alpha-trade/klines (1h, по 1000), без ключа, ~2 запроса в секунду.
Итог: s256/alpha/<фьючерс>.json {alphaId, listing, k: [[открытие мс, close, quote volume, trades]]}, s256/map.json.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s256/fetch.py"""
import json
import os
import pickle
import re
import time
import urllib.request

UA = {"User-Agent": "research-script/1.0"}
URL = "https://www.binance.com/bapi/defi/v1/public/alpha-trade/klines?symbol={}USDT&interval=1h&limit=1000&startTime={}"
END = 1792368000000            # 19.10.2026


def base(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    return (m.group(2), {"1000000": 1e6, "100000": 1e5, "10000": 1e4, "1000": 1e3, "1M": 1e6}[m.group(1)]) \
        if m and not m.group(2)[0].isdigit() else (fs, 1.0)


def get(url):
    for i in range(5):
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())
            time.sleep(0.45)
            return d.get("data") or []
        except Exception as e:  # noqa: BLE001
            print("  сбой", type(e).__name__, "пауза", 5 + 10 * i, flush=True)
            time.sleep(5 + 10 * i)
    return None


def klines(aid, t0):
    out, t = [], t0
    while t < END:
        d = get(URL.format(aid, t))
        if d is None:
            return None
        if not d:
            break
        out += [[int(x[0]), float(x[4]), float(x[7]), int(x[8])] for x in d]
        nt = int(d[-1][0]) + 3600000
        if nt <= t or len(d) < 1000:
            break
        t = nt
    return out


def main():
    A = json.load(open("s252/alpha_tokens.json"))
    A = A.get("data") if isinstance(A, dict) else A
    SD = json.load(open("s252/spot_dates.json"))
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    by = {}
    for x in A:
        by.setdefault(str(x["symbol"]).upper(), []).append(x)
    mp = json.load(open("s256/map.json")) if os.path.exists("s256/map.json") else {}
    for fs in sorted(PU):
        if fs in mp or not len(PU[fs]) or fs not in K:
            continue
        coin, mult = base(fs)
        s0 = [v for v in (SD.get(coin), SD.get(fs)) if v]
        for k in {fs, coin}:
            a = SP.get(k)
            if a is not None and len(a) and (a[:, 1] > 0).any():
                s0.append(float(a[a[:, 1] > 0, 0].min()))
        spot0 = min(s0) if s0 else None
        cands = by.get(coin.upper(), [])
        if not cands:
            mp[fs] = None; continue
        k = K[fs]; kt = k["t"].astype("int64"); live = k["qv"] > 0
        best = None
        for c in sorted(cands, key=lambda c: -float(c.get("marketCap") or 0)):
            ks = klines(c["alphaId"], int(c["listingTime"]))
            if not ks:
                continue
            ah = {x[0] // 1000: x[1] for x in ks}
            common = [int(t) for t in kt[live] if int(t) % 3600 == 2700 and int(t) - 2700 in ah]   # последняя свеча часа
            if not common:
                continue
            tl = common[-1]; i = int(re.sub("", "", str(int((kt == tl).argmax()))))
            r = ah[tl - 2700] * mult / float(k["c"][i])
            if 0.8 <= r <= 1.25:
                best = c
                json.dump({"alphaId": c["alphaId"], "listing": int(c["listingTime"]), "spot0": spot0, "k": ks,
                           "mulPoint": c.get("mulPoint"), "chain": c.get("chainName")}, open(f"s256/alpha/{fs}.json", "w"))
                break
        mp[fs] = best["alphaId"] if best else None
        print(fs, "→", mp[fs], flush=True)
        json.dump(mp, open("s256/map.json", "w"))
    print("сопоставлено:", sum(1 for v in mp.values() if v), "из", len(mp))


if __name__ == "__main__":
    main()
