"""s36 — листинг на Hyperliquid при живом фьючерсе Binance (гипотеза — ВЫВОДЫ.md, записана до проверки).
Время листинга — первая часовая свеча перпа Hyperliquid (`candleSnapshot`: сначала суточные с 0, потом часовые в первые
двое суток). Монета Hyperliquid → фьючерс Binance как в s27 (hl_positions.binance). Событие — листинг после 01.01.2025,
фьючерс Binance торгуется ≥ 1 сут. Шорт фьючерса на закрытии часа после первой свечи, 7 сут, стоп +50%, комиссия 0,1%,
фактический фандинг (s15/common.trade); плацебо — та же монета за 45/90/135 сут; половины до и после 01.12.2025;
пересечение с корейскими листингами (s15/kr_listings.pkl) и 🅱️ (s22/h10_ann.pkl) за ±3 сут. Кэш свечей — s36/first.json.
Запуск из папки с данными, после выгрузки s27 (общий лимит запросов Hyperliquid)."""
import json
import os
import pickle
import sys
import time
import urllib.request
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, os.path.join(HERE, "..", "s27"))
from common import K, fut_of, live, trade  # noqa: E402

DAY, H = 86400, 3600
CUT = 1764547200
T_FROM = 1735689600                                         # 01.01.2025
PL = (45, 90, 135)
API = "https://api.hyperliquid.xyz/info"


def post(body):
    for i in range(5):
        try:
            r = urllib.request.urlopen(urllib.request.Request(API, data=json.dumps(body).encode(),
                                                              headers={"Content-Type": "application/json"}), timeout=60)
            return json.loads(r.read())
        except Exception:
            time.sleep(5 + 5 * i)
    return None


def first_candles(coins):
    path = "s36/first.json"
    D = json.load(open(path)) if os.path.exists(path) else {}
    now = int(time.time() * 1000)
    for n, c in enumerate(coins):
        if c in D:
            continue
        d = post({"type": "candleSnapshot", "req": {"coin": c, "interval": "1d", "startTime": 0, "endTime": now}})
        time.sleep(1.5)
        if not d:
            D[c] = None; continue
        t0 = min(x["t"] for x in d)
        h = post({"type": "candleSnapshot", "req": {"coin": c, "interval": "1h", "startTime": t0, "endTime": t0 + 2 * DAY * 1000}})
        time.sleep(1.5)
        D[c] = min(x["t"] for x in h) / 1000 if h else t0 / 1000
        if n % 25 == 0:
            json.dump(D, open(path, "w")); print(f"  {n}/{len(coins)}", flush=True)
    json.dump(D, open(path, "w"))
    return D


def binance_of(coin):
    if ":" in coin or "@" in coin or "/" in coin:
        return None
    cands = []
    if coin.startswith("k") and coin[1:].isupper():
        cands += ["1000" + coin[1:], coin[1:]]
    cands += [coin, {"RNDR": "RENDER", "MATIC": "POL"}.get(coin, coin), "1000" + coin]
    for c in cands:
        if c in K:
            return c
    return None


def idx(s, te):
    t = K[s]["t"]; i = int(np.searchsorted(t, te - 900))
    return i if i < len(t) and t[i] == te - 900 else None


def short(s, te):
    i = idx(s, te)
    if i is None:
        return None
    r = trade(s, i, tp=None, sl=0.5, hold_h=168, side=-1)
    return r["net"] if r else None


def ct(x, T):
    d = pd.Series(np.asarray(x, float), index=pd.to_datetime(np.asarray(T), unit="s").date).dropna()
    if len(d) < 5:
        return np.nan, np.nan, len(d)
    q = d.groupby(level=0).mean()
    return d.mean(), (q.mean() / q.std() * np.sqrt(len(q)) if len(q) > 2 and q.std() > 0 else np.nan), len(d)


if __name__ == "__main__":
    meta = post({"type": "meta"})
    coins = [u["name"] for u in meta["universe"]]
    print("перпов Hyperliquid в meta:", len(coins))
    F = first_candles(coins)
    kr = pd.DataFrame(pickle.load(open("s15/kr_listings.pkl", "rb"))); kr["s"] = [fut_of(b)[0] for b in kr.base]
    bl = pd.read_pickle("s22/h10_ann.pkl")
    rows = []
    for c, t in F.items():
        if not t or t < T_FROM:
            continue
        s = binance_of(c)
        if s is None:
            continue
        lo, hi = live(s)
        if lo > t - DAY or hi < t:
            continue
        te = (int(t) // H + 2) * H                         # закрытие часа после первой свечи
        n = short(s, te)
        if n is None:
            continue
        p = [short(s, te - d * DAY) for d in PL]; p = [x for x in p if x is not None]
        ov = "кор" if ((kr.s == s) & ((kr.t - t).abs() <= 3 * DAY)).any() else "bin" if ((bl.s == s) & ((bl["T"] - t).abs() <= 3 * DAY)).any() else ""
        rows.append(dict(c=c, s=s, t=t, te=te, net=n, plac=np.mean(p) if p else np.nan, ov=ov))
    D = pd.DataFrame(rows)
    pickle.dump(D, open("s36/events.pkl", "wb"))
    print(f"событий: {len(D)} (корейский листинг ±3 сут — {(D.ov == 'кор').sum()}, 🅱️ — {(D.ov == 'bin').sum()})")
    for lab, x in (("все", D), ("без корейских и 🅱️", D[D.ov == ""])):
        m, tt, n = ct(x.net, x.te)
        h1, h2 = x[x.te < CUT].net, x[x.te >= CUT].net
        print(f"  {lab}: n={n} {m:+.2%} (t {tt:+.1f}), медиана {x.net.median():+.2%}, в плюсе {(x.net > 0).mean():.0%}, стопов "
              f"{(x.net < -0.45).mean():.0%} | половины {h1.mean():+.2%} ({len(h1)}) / {h2.mean():+.2%} ({len(h2)}) | плацебо {x.plac.mean():+.2%}")
